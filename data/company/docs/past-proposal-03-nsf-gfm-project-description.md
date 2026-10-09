> Synthetic document for grant-capture-agent evaluation. All people, numbers and results are fictional.

# NSF SBIR Phase I (2024): Project Description
## Grid-forming control for weak grids

### Overview

As more solar and storage connect through inverters, parts of the distribution system have become weak: the grid voltage moves a lot when current changes, and conventional inverters that follow the grid voltage can become unstable. Grid-forming inverters set their own voltage and frequency and can hold up a weak feeder, but their behavior during faults is a known difficulty. Their current must be limited to protect the silicon-carbide switches, and the limiting action can make the inverter lose synchronism or trip when it should stay connected. We proposed a new current-limiting and recovery method for the HelioLink 250 that keeps the inverter connected through faults on weak feeders.

### Intellectual merit

The project addresses an open question in grid-forming control: how to limit fault current without losing voltage control. Existing methods either switch the control mode during a fault, which causes transients on exit, or use a fixed virtual impedance that is too conservative for weak grids. Our approach adjusts the virtual impedance continuously, based on a running estimate of the grid strength. This lets the inverter supply more support to the feeder when the grid is strong and back off smoothly when it is weak. We will establish the stability boundaries of the method through analysis and then confirm them on a hardware-in-the-loop rig and a 500 kW regenerative grid simulator. The results will be published so other groups can reproduce them.

### Broader impacts

Weak-grid operation limits how much solar and storage rural cooperatives can add. A control method that makes inverters stay online during faults helps these utilities connect more local generation without costly feeder upgrades. The project will also support two summer undergraduate interns from Colorado School of Mines, where the company is an STTR research partner, and we will release our test procedure and anonymized waveforms for use in teaching.

### Technical objectives

1. Derive an online grid-strength estimator that converges within 100 ms of a disturbance.
2. Design an adaptive virtual impedance controller that stays stable for short-circuit ratios from 1.5 to 5.
3. Show at least 10% faster fault ride-through than a baseline fixed-impedance controller under the same test conditions.
4. Document the test procedure so an independent laboratory can repeat it.

### Milestones

| Month | Milestone |
|---|---|
| 2 | Grid-strength estimator specified and simulated |
| 4 | Adaptive controller running on the OPAL-RT rig |
| 6 | Baseline and adaptive controllers compared on the HelioLink 250 prototype using the grid simulator |
| 8 | Final report, test procedure and Phase II plan delivered |

### Team and approach

Ravi Deshmukh will lead the control design with Dr. Maya Okafor as Principal Investigator. Jordan Lee will run the test campaigns. Our hardware-in-the-loop work lets us find problems in simulation first, which lowers the risk of damaging hardware. Front Range Utility Cooperative has agreed to provide feeder data to make the test scenarios realistic.

### Related work and gap

Published grid-forming methods fall into three groups. Droop-based controllers are simple but have weak fault behavior. Virtual synchronous machine controllers model inertia but still need current limiting. Virtual impedance methods limit current well but use fixed values chosen for a nominal grid. We found few studies of adaptive virtual impedance tested on real hardware below a short-circuit ratio of 2, and almost none that report repeatable test conditions. This gap is where our results should add the most.

### Risk and mitigation

The main technical risk is that the grid-strength estimator becomes noisy during a fault, which would make the impedance change in the wrong direction. We will limit the rate of change of the impedance and freeze the estimate during a fault. A second risk is damage to hardware during early tests, which we will reduce by running every new controller on the hardware-in-the-loop rig first and by starting at 25% power on the grid simulator.

### Commercial potential

The HelioLink 250 is a 250 kW silicon-carbide inverter with 98.7% peak efficiency. Rural cooperatives are the first target market. A controller that improves ride-through on weak feeders is a direct selling point, and we will use the Phase I results to support a field pilot and a Phase II proposal.
