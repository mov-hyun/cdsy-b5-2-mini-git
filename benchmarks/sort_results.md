# Sorting benchmark

Environment: CPython 3.12.14, Windows AMD64.
Seed: 20261004. Warmups per case: 1. Measured runs per algorithm and case: 5.
Timing: arithmetic mean in milliseconds; perf_counter_ns; alternating algorithm order.
Inputs: integer lists. Data generation, output validation and I/O are outside timing.
Each timed call includes input copying, key calculation and sorting.

| Input | n | Merge mean (ms) | Insertion mean (ms) | Insertion / merge |
| --- | ---: | ---: | ---: | ---: |
| random | 100 | 0.097800 | 0.187820 | 1.92x |
| random | 500 | 0.799580 | 5.969720 | 7.47x |
| random | 1000 | 1.417340 | 21.548200 | 15.20x |
| random | 2000 | 3.072120 | 79.793040 | 25.97x |
| random | 4000 | 7.002540 | 344.496660 | 49.20x |
| ordered | 100 | 0.100660 | 0.017600 | 0.17x |
| ordered | 500 | 0.548520 | 0.086900 | 0.16x |
| ordered | 1000 | 1.226440 | 0.179840 | 0.15x |
| ordered | 2000 | 2.688120 | 0.427660 | 0.16x |
| ordered | 4000 | 5.852600 | 0.842260 | 0.14x |
| reversed | 100 | 0.085260 | 0.375900 | 4.41x |
| reversed | 500 | 0.522760 | 9.560680 | 18.29x |
| reversed | 1000 | 1.147980 | 40.271680 | 35.08x |
| reversed | 2000 | 2.507000 | 165.570660 | 66.04x |
| reversed | 4000 | 5.245440 | 650.720920 | 124.05x |
| duplicates | 100 | 0.092740 | 0.194420 | 2.10x |
| duplicates | 500 | 0.571200 | 3.897820 | 6.82x |
| duplicates | 1000 | 1.280500 | 17.036640 | 13.30x |
| duplicates | 2000 | 2.944500 | 73.404980 | 24.93x |
| duplicates | 4000 | 6.620540 | 301.968320 | 45.61x |

Raw samples are stored in the adjacent JSON file.
These are local measurements, not general performance guarantees or full LOG timings.
