> Synthetic document for grant-capture-agent evaluation. All people, numbers and results are fictional.

# DOE SBIR Phase I Final Report (2023)
## Degradation-aware BMS for second-life batteries

**Award:** $200,000 | **Principal Investigator:** Dr. Maya Okafor | **Performer:** Lumen Grid Labs, LLC

### Summary

The project built and tested a degradation-aware version of the LGL-BMS3 battery management system on two packs made from retired electric-vehicle modules. All Phase I milestones were met on schedule. The prototype balanced cells to within plus or minus 2 mV, held state-of-charge estimation error at or below 1.5%, and reduced the spread in cell ageing rate compared with a standard balancing method.

### Results against milestones

| Milestone | Target | Result | Status |
|---|---|---|---|
| Characterize retired modules | 32 cells measured | 32 cells measured, 2 rejected as outliers | Met |
| Cell balancing accuracy | within plus or minus 2 mV | plus or minus 1.8 mV at rest, worst case over 50 balancing events | Met |
| State-of-charge error | 1.5% or lower | 1.3% root-mean-square, 1.5% worst case over a mixed duty cycle | Met |
| Ageing spread reduction | at least 20% | 27% lower spread in capacity fade after 300 cycles | Met |
| Firmware on LGL-BMS3 hardware | running in real time | estimator runs at 10 Hz using 38% of the processor | Met |

### Measured performance

Two 16-cell packs were cycled for 300 cycles at 25 degrees C with a mixed duty cycle of charge, discharge and rest. One pack used standard voltage balancing and the other used the degradation-aware rule. After 300 cycles, the standard pack's cells showed a capacity spread of 6.4 percentage points, and the degradation-aware pack showed 4.7, which is the 27% reduction reported above.

Cell balancing was tested by deliberately offsetting cell voltages by up to 80 mV and measuring the residual after 40 minutes of balancing. The largest residual in 50 events was 1.8 mV.

State-of-charge error was measured against coulomb-counted reference values from a calibrated cycler. Estimation error stayed at or below 1.5% in all test runs, including runs that began at a wrong initial estimate of 20 percentage points.

### Lessons learned

1. **Retired modules need characterization first.** Two of 32 cells were far outside the group and were removed. Without this step the estimator would have been tuned to bad data.
2. **Temperature matters more than expected.** The open-circuit voltage curve shifted enough between 15 and 35 degrees C to add about 0.6 points of estimation error until we added temperature compensation.
3. **The 2 A balancing stage is a limit.** Packs with a wide capacity spread need more balancing current than the stage provides. A Phase II design should raise the limit.
4. **Documentation takes time.** Recording every test condition added about two weeks, but it made later comparison between packs possible.

### Next steps

We recommend a Phase II effort to build 20 pack controllers, raise the balancing current, extend testing to 1,000 cycles, and run a field trial with a utility partner.

### Test method details

The retired modules were sourced from a single salvage supplier and had been in vehicle service for between four and six years. Before the project we recorded each cell's capacity at a C/3 rate, its internal resistance at 50% charge, and its voltage rest curve. Capacity ranged from 71% to 86% of nameplate, and resistance ranged from 1.4 to 2.3 times the nameplate value. This wide spread is the reason standard balancing struggles on this type of pack.

The cycling regime was a one-hour charge, a mixed discharge with three power levels, and a 30-minute rest. Cell temperatures were held to within 1 degree C of set point by the thermal chamber. The reference cycler's current accuracy was 0.05% of reading, and its calibration certificate was dated within the previous twelve months.

### Deviations from plan

Two items differed from the proposal. The firmware port took five weeks instead of three because the estimator needed a fixed-point rewrite. We recovered the time by running the 300-cycle test in parallel on both packs. The 1,000-cycle target in the original plan was reduced to 300 cycles, because accelerated testing at 40 degrees C produced clear separation between the packs sooner than expected. Both changes were agreed with the DOE program manager.
