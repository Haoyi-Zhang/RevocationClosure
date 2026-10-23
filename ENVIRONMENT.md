# Execution environment and scope

Scientific commands use Python 3.10+ and its standard library, including SQLite, asyncio, gzip, socket, subprocess, and resource. Linux/POSIX is the tested execution family. Local socket and owned-process permissions are needed. Python assertions must be enabled. No third-party Python dependency, Java, external trace, private data, GPU, remote service, or online retrieval is required.

The original gateway harness runs one sequential emulator process and one owned asyncio server process. Five gateway sockets and five databases share that server process. Journal crash tests run one owned child at a time. Stateful journal tests reopen databases in their test process. The original campaign has one active command at a time and a 180-second command timeout; resumable chunks accommodate a shorter calling environment.

The separately retained process-separation study uses five simultaneous gateway child processes, one controller, and at most one additional short-lived collector child. All run on one host, using owned loopback sockets and disposable SQLite databases. It terminates only its own children. It uses Python standard-library interfaces available on Windows and POSIX, does not import the POSIX resource interface, and does not add a measured process-resource result to the original campaign. Keys, actors and clocks remain harness inputs.

Reproduction retains the exact executable root and test Python source set and command logs. It compares scientific decisions, structured inputs, and ordered collector traces, not timing equality. Results report scoped process CPU/RSS where collected. No whole-session global memory peak or cumulative human-session CPU figure is asserted.

Paper builds additionally require pdfLaTeX, BibTeX (or the equivalent installed `bibtex.original` entry), standard AMS/graphics packages, TikZ, and PGFPlots. IEEEtran class and bibliography-style files are supplied unmodified with their license notices. Font files are not redistributed.
