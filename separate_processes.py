"""Owned loopback/process recovery study; no production identity or time service.

Five gateway processes run on one host. Only children created by this driver
are terminated. All actor identities, keys and bounded clocks remain fixtures.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import tempfile
import threading

from capability import Store, N, MAX_WIRE, MAX_REPLY_WIRE, barrier, grant, packed, revocation
from collector import ClosureJournal
from collector_reference import DurableReference
from verifier import verify_decision


def require(condition,message):
    if not condition:raise ValueError(message)


def gateway(db,node,mode):
    require(type(node) is int and 0<=node<N,'gateway identity')
    with ExitStack() as cleanup:
        store=Store(db,node,2,mode)
        cleanup.callback(store.close)
        listener=cleanup.enter_context(socket.socket())
        listener.bind(('127.0.0.1',0));listener.listen(4);listener.settimeout(30)
        print(json.dumps({'port':listener.getsockname()[1],'pid':os.getpid(),'node':node}),flush=True)
        for _ in range(256):
            try:connection,_=listener.accept()
            except socket.timeout:break
            with connection:
                connection.settimeout(10)
                try:
                    with connection.makefile('rb') as stream:line=stream.readline(MAX_WIRE+1)
                    require(len(line)<=MAX_WIRE and line.endswith(b'\n'),'request framing')
                    request=json.loads(line)
                    require(type(request) is dict and type(request.get('node')) is int and request['node']==node,'request gateway')
                    op=request.get('op')
                    require(op in {'ingest','use','stats'},'operation')
                    if op!='stats':store.set_clock(request['clock'])
                    if op=='ingest':value=store.ingest(request['events'])
                    elif op=='use':value=store.authorize(request['cap'],request['actor'],1,'svc0',True)
                    else:value=store.stats()
                    reply=packed({'ok':True,'value':value})+b'\n'
                    require(len(reply)<=MAX_REPLY_WIRE,'reply framing')
                except (ValueError,KeyError,TypeError) as exc:
                    reply=packed({'ok':False,'error':str(exc)})+b'\n'
                connection.sendall(reply)


def child_flags():
    return subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0


class Worker:
    def __init__(self,db,node,mode='closed'):
        self.db,self.node,self.mode=Path(db),node,mode
        self.process=None
        self.start()

    def start(self):
        self.process=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),
            'gateway','--db',str(self.db),'--node',str(self.node),'--mode',self.mode],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',
            creationflags=child_flags())
        lines=queue.Queue()
        threading.Thread(target=lambda:lines.put(self.process.stdout.readline()),daemon=True).start()
        try:
            line=lines.get(timeout=10)
            require(bool(line),'gateway startup failed')
            self.identity=json.loads(line)
            require(self.identity['pid']==self.process.pid and self.identity['node']==self.node,'process identity')
        except BaseException:
            self.close();raise

    def rpc(self,request):
        request=dict(request,node=self.node)
        with socket.create_connection(('127.0.0.1',self.identity['port']),timeout=10) as connection:
            connection.sendall(packed(request)+b'\n')
            with connection.makefile('rb') as stream:line=stream.readline(MAX_REPLY_WIRE+1)
        require(len(line)<=MAX_REPLY_WIRE and line.endswith(b'\n'),'reply framing')
        reply=json.loads(line)
        require(reply.get('ok') is True,'gateway rejected: '+str(reply.get('error')))
        return reply['value']

    def close(self):
        if self.process is None:return
        if self.process.poll() is None:self.process.kill()
        self.process.wait(timeout=10)
        self.process.stdout.close();self.process.stderr.close()
        self.process=None

    def restart(self):
        self.close();self.start()


def collector_child(db,request):
    with ClosureJournal(db,request['revocation'],2) as journal:
        result=journal.observe(request['clock'],request['receipts'],request['failpoint'])
    print(json.dumps(result,sort_keys=True),flush=True)


def run_collector(db,revoke,clock,receipts,failpoint):
    request={'revocation':revoke,'clock':clock,'receipts':receipts,'failpoint':failpoint}
    result=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'collector','--db',str(db)],
        input=json.dumps(request),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
        encoding='utf-8',timeout=20,creationflags=child_flags())
    require(result.returncode==(70 if failpoint else 0),'collector exit: '+result.stderr)
    if failpoint:require(result.stdout=='','failure unexpectedly released a reply')
    return {'clock':clock,'failpoint':failpoint,'returncode':result.returncode,
            'stdout':result.stdout,'stderr':result.stderr}


def study():
    raw={'parent_pid':os.getpid(),'worker_starts':[],'rpc':[],'collector_processes':[]}
    root=grant(0,1,None,7,[2000]*N,'separate-root')
    deadlines=[1000,1000,1000,40,40]
    target=grant(1,2,root,3,deadlines,'separate-target')
    child=grant(2,3,target,1,deadlines,'separate-hidden-child')
    grandchild=grant(3,4,child,1,deadlines,'separate-hidden-grandchild')
    revoke=revocation(target)
    workers=[]
    def note_start(worker):raw['worker_starts'].append(dict(worker.identity,mode=worker.mode))
    def rpc(worker,request,phase):
        answer=worker.rpc(request)
        raw['rpc'].append({'node':worker.node,'phase':phase,'request':request,'answer':answer})
        return answer
    with tempfile.TemporaryDirectory(prefix='revocation-separate-') as temporary:
        directory=Path(temporary)
        try:
            for i in range(N):
                worker=Worker(directory/('gateway-'+str(i)+'.sqlite'),i)
                workers.append(worker);note_start(worker)
            require(len({w.process.pid for w in workers})==N,'gateways not process-separated')
            require(all(w.process.pid!=os.getpid() for w in workers),'gateway shares parent process')
            for worker in workers:rpc(worker,{'op':'ingest','clock':10,'events':[root,target]},'known-lineage')
            receipts=[]
            for worker in workers[:3]:receipts.extend(rpc(worker,{'op':'ingest','clock':20,'events':[revoke]},'durable-receipts')['receipts'])
            before=[w.process.pid for w in workers]
            workers[1].restart();note_start(workers[1])
            require(all(w.process.pid==before[i] and w.process.poll() is None for i,w in enumerate(workers) if i!=1),'another gateway was restarted')
            recovered=rpc(workers[1],{'op':'use','clock':21,'cap':target['id'],'actor':2},'after-one-process-loss')
            require(not recovered['allow'] and verify_decision(recovered),'receipt exclusion lost on gateway recovery')
            collector=directory/'collector.sqlite'
            for failpoint in ('before_commit','after_commit_before_reply'):
                raw['collector_processes'].append(run_collector(collector,revoke,42,receipts,failpoint))
                with ClosureJournal(collector,revoke,2) as journal:state=journal.status()
                require(state['closed']==(failpoint=='after_commit_before_reply'),'collector commit boundary')
                raw['collector_processes'][-1]['reopened_state']=state
            raw['collector_processes'].append(run_collector(collector,revoke,41,[],None))
            recovered_state=json.loads(raw['collector_processes'][-1]['stdout'])
            require(recovered_state['closed'] and recovered_state['lower_time']==40,'completion regressed after collector recovery')
            with DurableReference(directory/'reference.sqlite',revoke,2) as reference:
                reference.observe(42,receipts)
                require(reference.observe(41,[])==recovered_state,'same-information reference differs')
            post=[]
            for phase,clock in [('late-descendants',41),('after-all-gateway-recovery',43)]:
                if phase=='after-all-gateway-recovery':
                    for worker in workers:worker.restart();note_start(worker)
                for worker in workers:
                    rpc(worker,{'op':'ingest','clock':clock,'events':[root,target,child,grandchild]},phase)
                    for leaf,actor in ((child,3),(grandchild,4)):
                        answer=rpc(worker,{'op':'use','clock':clock,'cap':leaf['id'],'actor':actor},phase)
                        require(not answer['allow'] and verify_decision(answer),'post-completion authorization')
                        post.append({'phase':phase,'node':worker.node,'depth':1 if actor==3 else 2,
                                     'allow':answer['allow'],'reason':answer['reason']})
            stateless=[barrier(revoke,receipts,clock,2)['closed'] for clock in (42,41)]
            require(stateless==[True,False],'stateless control')
        finally:
            for worker in workers:worker.close()
        volatile=Worker(directory/'volatile.sqlite',0,'volatile')
        try:
            note_start(volatile)
            rpc(volatile,{'op':'ingest','clock':20,'events':[root,target,child,revoke]},'volatile-control')
            require(not rpc(volatile,{'op':'use','clock':21,'cap':child['id'],'actor':3},'volatile-before-recovery')['allow'],'volatile control did not exclude')
            volatile.restart();note_start(volatile)
            resurrected=rpc(volatile,{'op':'use','clock':22,'cap':child['id'],'actor':3},'volatile-after-recovery')['allow']
            require(resurrected,'volatile control did not expose lost exclusion')
        finally:volatile.close()
    summary={'gateways_concurrently_process_separated':5,'hosts':1,'gateway_restart_events_positive':6,
             'collector_fault_events':2,'postcompletion_checks':len(post),'postcompletion_allows':0,
             'postcompletion_decisions':post,'collector_clock_regression_retained_lower':40,
             'same_information_reference_equal':True,'stateless_control_closed':stateless,
             'volatile_control_resurrected':resurrected,
             'identity_and_clock_source':'public fixture authentication and harness-supplied bounded clocks'}
    return summary,raw


def verify_records(summary,raw):
    """Recheck retained decisions and the process/transaction witness, not timings."""
    require(type(summary) is dict and type(raw) is dict,'record shape')
    starts=raw['worker_starts']
    require(len(starts)==13,'worker start count')
    initial=starts[:5]
    require([x['node'] for x in initial]==list(range(5)),'initial gateway coordinates')
    require(len({x['pid'] for x in initial})==5,'initial processes not distinct')
    require(all(type(x['pid']) is int and x['pid']!=raw['parent_pid'] and
                type(x['port']) is int and 0<x['port']<65536 for x in starts),'process identities')
    require([x['node'] for x in starts[5:11]]==[1,0,1,2,3,4] and
            all(x['mode']=='closed' for x in starts[:11]) and
            all(x['mode']=='volatile' for x in starts[11:]),'restart identities')
    faults=raw['collector_processes']
    require(len(faults)==3 and [x['returncode'] for x in faults]==[70,70,0],'collector exits')
    require([x['failpoint'] for x in faults]==['before_commit','after_commit_before_reply',None],
            'collector fault boundaries')
    require(faults[0]['stdout']==faults[1]['stdout']=='' and
            faults[0]['reopened_state']['closed'] is False and
            faults[1]['reopened_state']['closed'] is True,'commit-before-reply states')
    state=json.loads(faults[2]['stdout'])
    require(state['closed'] is True and state['lower_time']==40,'retained lower-time evidence')
    post=[]
    for row in raw['rpc']:
        if row['request']['op']!='use':continue
        answer=row['answer']
        if row['phase']=='volatile-before-recovery':
            require(answer['allow'] is False,'volatile pre-recovery control')
        elif row['phase']!='volatile-after-recovery':
            require(answer['allow'] is False and verify_decision(answer),'invalid denial snapshot')
        if row['phase'] in {'late-descendants','after-all-gateway-recovery'}:
            require(row['request']['clock']==(41 if row['phase']=='late-descendants' else 43),
                    'post-completion clock')
            post.append({'phase':row['phase'],'node':row['node'],
                         'depth':1 if row['request']['actor']==3 else 2,
                         'allow':answer['allow'],'reason':answer['reason']})
    require(len(post)==20 and len({(x['phase'],x['node'],x['depth']) for x in post})==20,
            'post-completion product')
    require(post==summary['postcompletion_decisions'],'summary/decision mismatch')
    require(summary['postcompletion_checks']==20 and summary['postcompletion_allows']==0,
            'decision totals')
    for key,value in {'gateways_concurrently_process_separated':5,'hosts':1,
            'gateway_restart_events_positive':6,'collector_fault_events':2,
            'collector_clock_regression_retained_lower':40,'same_information_reference_equal':True,
            'stateless_control_closed':[True,False],'volatile_control_resurrected':True,
            'identity_and_clock_source':'public fixture authentication and harness-supplied bounded clocks'}.items():
        require(type(summary[key]) is type(value) and summary[key]==value,'summary scope: '+key)
    volatile=[x for x in raw['rpc'] if x['phase']=='volatile-after-recovery']
    require(len(volatile)==1 and volatile[0]['answer']['allow'] is True,'volatile control')
    return True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    worker=sub.add_parser('gateway');worker.add_argument('--db',type=Path,required=True)
    worker.add_argument('--node',type=int,required=True);worker.add_argument('--mode',choices=['closed','volatile'],default='closed')
    collector=sub.add_parser('collector');collector.add_argument('--db',type=Path,required=True)
    replay=sub.add_parser('run');replay.add_argument('--out',type=Path,required=True)
    replay.add_argument('--compare',type=Path)
    check=sub.add_parser('verify');check.add_argument('--directory',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='gateway':gateway(args.db,args.node,args.mode)
    elif args.command=='collector':collector_child(args.db,json.load(sys.stdin))
    elif args.command=='verify':
        verify_records(json.loads((args.directory/'summary.json').read_text()),
                       json.loads((args.directory/'process-records.json').read_text()))
        print('Retained five-process recovery witness verified')
    else:
        require(not args.out.exists(),'choose a fresh output directory')
        summary,raw=study()
        verify_records(summary,raw)
        if args.compare:require(summary==json.loads(args.compare.read_text(encoding='utf-8')),'process study replay differs')
        args.out.mkdir(parents=True)
        for name,value in [('summary.json',summary),('process-records.json',raw)]:
            (args.out/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:v for k,v in summary.items() if k!='postcompletion_decisions'},sort_keys=True))


if __name__=='__main__':main()
