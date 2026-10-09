> Synthetic document for grant-capture-agent evaluation. All people, numbers and results are fictional.

# NSF SBIR Phase I Final Report (2024)
## Grid-forming control for weak grids

**Award:** $275,000 | **Principal Investigator:** Dr. Maya Okafor | **Performer:** Lumen Grid Labs, LLC

### Summary

The project developed an adaptive virtual impedance controller for the HelioLink 250 grid-forming inverter and compared it with a fixed-impedance baseline controller. Under identical test conditions, the adaptive controller completed fault ride-through 14% faster than the baseline and stayed connected in every test where the baseline tripped at the weakest grid setting.

### Results against objectives

| Objective | Target | Result |
|---|---|---|
| Grid-strength estimator convergence | within 100 ms | 82 ms median, 97 ms worst case |
| Stable operation range | short-circuit ratio 1.5 to 5 | stable across the full range in 120 of 120 runs |
| Fault ride-through improvement | at least 10% faster | 14% faster than baseline |
| Repeatable test procedure | documented | procedure issued as version 1.0 |

### Test conditions

All tests used the 500 kW regenerative grid simulator connected to the HelioLink 250 at 250 kW rated output, with the controller code running on the OPAL-RT rig for the first four months and on the inverter's own processor afterwards. Faults were three-phase voltage sags to 0.2 per unit lasting 150 ms. We tested five short-circuit ratios (1.5, 2, 3, 4 and 5) and, at each ratio, ran 12 faults per controller at initial loads of 50% and 100% of rating. Fault ride-through time was defined as the time from fault clearance until real power returned to 90% of its pre-fault value.

### Measured results

At a short-circuit ratio of 2, the baseline controller needed a median of 121 ms to recover to 90% power, and the adaptive controller needed 104 ms, which is 14% faster. The improvement was smaller at strong-grid settings, about 4% at a ratio of 5, and larger at weak settings. At a ratio of 1.5, the baseline tripped in 5 of 12 runs at full load, and the adaptive controller tripped in none.

Peak fault current stayed below 1.5 times rated current in all runs, within the silicon-carbide switch limit.

### Limitations

The tests used a simulated grid, not a live feeder. Only three-phase symmetrical faults were tested, so unbalanced faults remain future work. The grid-strength estimator was less accurate when the grid already carried large harmonic distortion.

### Next steps

Phase II work should add unbalanced faults and harmonics, repeat the tests at an independent laboratory, and move to a field deployment. The 2025 pilot with Front Range Utility Cooperative began that step.

### Controller description

The baseline controller used a fixed virtual impedance of 0.25 per unit during faults. The adaptive controller used the same value at a short-circuit ratio of 3 and scaled it between 0.15 and 0.35 per unit as the estimated ratio changed. The estimator injected a small 5 Hz probing signal and measured the voltage response, which converges faster than waiting for natural disturbances. The probing signal added less than 0.3% total harmonic distortion to the output voltage.

### Statistical treatment

Each condition was run 12 times per controller. We report medians because recovery times were slightly skewed by occasional slow recoveries. The 14% figure compares median recovery times at a ratio of 2 and full load. At 95% confidence, the interval for the improvement was 11% to 17% based on a bootstrap over the 12 runs. Test order was randomized to avoid thermal drift effects, and the inverter was allowed to cool for ten minutes between full-load faults.

### Deviations from plan

The first firmware build on the inverter processor missed the 100 ms estimator deadline by a small margin. Ravi Deshmukh reduced the sample window, which restored the deadline at a small cost in accuracy. The test campaign finished one week later than planned, and the final report was delivered on time.
