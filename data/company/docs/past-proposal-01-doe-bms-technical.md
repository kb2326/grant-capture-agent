> Synthetic document for grant-capture-agent evaluation. All people, numbers and results are fictional.

# DOE SBIR Phase I (2023): Technical Approach
## Degradation-aware BMS for second-life batteries

### The problem

Electric-vehicle batteries are usually retired when they fall to about 70 to 80% of their original capacity. Many of these modules still work well enough for stationary storage, but they are a poor fit for a standard battery management system. Retired modules differ from each other in capacity, internal resistance and rate of further ageing. A pack that treats them as identical cells will be limited by its weakest module, and a weak cell that is over-worked will fail early. Today, utilities and storage integrators either discard most retired modules or accept short pack life and large safety margins.

### The innovation

We proposed to extend our LGL-BMS3 battery management system with a degradation-aware layer. Existing balancing logic equalizes voltage. Ours would also estimate each cell's remaining capacity and ageing rate online, and then shift current away from the cells that are ageing fastest. The estimator uses incremental capacity features from normal charge cycles, so it needs no special diagnostic cycles and no extra sensors.

### Technical objectives

1. **Balance cells to within plus or minus 2 mV** at rest, including packs with mixed capacities.
2. **Hold state-of-charge estimation error at or below 1.5%** over a mixed duty cycle on retired modules.
3. **Reduce the spread in cell ageing rate** across a pack by directing current according to estimated remaining capacity.

### Work plan

**Task 1: Test pack and baseline (months 1 to 2).** Assemble two 16-cell packs from retired electric-vehicle modules and measure baseline capacity and resistance for every cell. Lead: Elena Brandt.

**Task 2: Estimator development (months 2 to 4).** Build and tune the capacity and ageing estimator using recorded cycling data. Lead: Elena Brandt, with Dr. Maya Okafor on control integration.

**Task 3: Firmware integration (months 3 to 5).** Port the estimator and the degradation-aware balancing rule onto the LGL-BMS3 hardware. Lead: Ravi Deshmukh.

**Task 4: Validation (months 5 to 6).** Cycle both packs against the baseline and report balancing accuracy, estimation error and ageing spread. Lead: Jordan Lee.

### Risks and mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Retired modules arrive with unknown history | High | Medium | Run a full characterization before use and reject outliers |
| Estimator is too slow for the embedded processor | Medium | High | Use a reduced feature set and fixed-point arithmetic |
| Ageing differences are too small to measure in six months | Medium | Medium | Use accelerated cycling at elevated temperature |
| Balancing hardware limits current redistribution | Low | Medium | Use the existing 2 A balancing stage and cap the rule accordingly |

### Expected outcome

At the end of Phase I we expected a working LGL-BMS3 prototype with the new layer, measured data on two packs, and a clear estimate of the pack life gained, which would feed the Phase II plan.

### Background and prior work

Lumen Grid Labs developed the LGL-BMS3 as a commercial-grade management system for new cells, and it already balances cells to within plus or minus 2 mV with state-of-charge error at or below 1.5% on matched cells. Phase I would test whether these figures can be held on retired modules, which is a much harder case because each cell has a different capacity and resistance. Dr. Elena Brandt's earlier work on incremental capacity features showed that capacity can be estimated from ordinary charging, and the patent application on ranking retired cells covers the first step of that approach.

### Test and measurement plan

Each test pack will contain 16 cells in series. Voltage will be measured on every cell with a resolution of 0.5 mV, and pack current will be measured with a calibrated shunt. Capacity will be checked against a reference cycler at the start, middle and end of the project, so that estimator drift can be separated from real ageing. The baseline pack will use standard voltage balancing and the test pack will use the degradation-aware rule, and both packs will see the same duty cycle in the same thermal chamber, so that the only intended difference is the control method. Cycling will run at 25 degrees C, with an accelerated segment at 40 degrees C.

### Success criteria

Phase I will be judged a success if the prototype meets objectives 1 and 2 above, shows a measurable reduction in ageing spread against the baseline pack, and runs the estimator in real time on the LGL-BMS3 processor. We set the ageing spread target at a reduction of at least 20% in capacity fade spread after 300 cycles. These targets were chosen because they are measurable within the six-month period and matter to integrators who buy second-life packs.

### Deliverables

The project will deliver a working prototype, a data set from both packs, a final report with all test conditions, and a Phase II plan with a cost and schedule estimate.
