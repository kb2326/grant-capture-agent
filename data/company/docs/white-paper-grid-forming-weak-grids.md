> Synthetic document for grant-capture-agent evaluation. All people, numbers and results are fictional.

# White Paper: Grid-Forming Control for Weak Grids (2025)

## 1. Executive Summary
Lumen Grid Labs, LLC (Golden, Colorado; founded 2019; 32 employees; 100% U.S.-owned; UEI LGLSYNTH0001) develops advanced power electronics and energy storage controls. This white paper highlights our grid-forming inverter control framework implemented on the HelioLink 250, a 250 kW SiC grid-forming inverter delivering 98.7% peak efficiency. Building directly on research supported by our NSF SBIR Phase I 2024 award ("Grid-forming control for weak grids", $275,000; 14% faster fault ride-through than baseline), this control scheme provides robust voltage and frequency stabilization on distribution feeders experiencing weak grid conditions.

## 2. Challenges in Weak Feeder Integration
Distribution feeders with high penetrations of inverter-based generation experience severe voltage fluctuations and low effective inertia. In rural and edge-of-grid distribution networks, high line impedances create conditions where a short-circuit ratio below 2 causes phase-locked loop (PLL) tracking instability in legacy grid-following inverters. Under these conditions, small load steps or line faults routinely trigger undervoltage trips and harmonic interactions.

## 3. HelioLink 250 Grid-Forming Control Framework
The HelioLink 250 replaces grid-following PLL loops with active virtual synchronous machine control and programmable droop dynamics. By establishing an internal voltage phasor, the inverter acts as an instantaneous voltage source, holding feeder frequency at 60 Hz and line voltage within 1.0% of nominal targets. When coupled with storage assets managed by our LGL-BMS3 solid-state battery management system (featuring cell balancing ±2 mV, SoC estimation error ≤ 1.5%), the system delivers sub-cycle active and reactive power support.

This work complements insights from our completed DOE SBIR Phase I 2023 award ("Degradation-aware BMS for second-life batteries", $200,000; met all milestones), ensuring that fast grid-forming power surges do not induce localized pack degradation.

## 4. Laboratory Validation and Performance Metrics
Experimental verification took place in our 1,800 sq ft power-electronics lab in Golden, Colorado. Using our 500 kW regenerative grid simulator and OPAL-RT hardware-in-the-loop rig, test engineer Jordan Lee conducted over 150 simulated fault and islanding scenarios. Power electronics CTO Ravi Deshmukh led control loop tuning, while lead battery scientist Elena Brandt supervised DC bus voltage margins. 

In testing where feeder impedance resulted in a short-circuit ratio below 2, the HelioLink 250 maintained continuous voltage stability and achieved 14% faster fault ride-through than baseline droop controls, restoring nominal voltage within 42 milliseconds of fault clearance.

## 5. Deployment and Utility Partnerships
Lumen Grid Labs is currently advancing pilot field configurations with Front Range Utility Cooperative (letter of support 2025) and our STTR research partner, Colorado School of Mines. Project leadership is provided by CEO Dr. Maya Okafor (CEO, PI on both awards).

## 6. Contact Information
- Dr. Maya Okafor, CEO & Principal Investigator: maya.okafor@example.com | 555-0144
- Ravi Deshmukh, CTO, Power Electronics: ravi.deshmukh@example.com | 555-0182
