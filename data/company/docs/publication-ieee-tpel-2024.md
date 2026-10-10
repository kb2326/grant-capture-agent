> Synthetic document for grant-capture-agent evaluation. All people, numbers and results are fictional.

# Journal Paper Summary: Advanced Grid-Forming Control for Weak Grids

**Publication Reference:** Okafor, M., Deshmukh, R., Lee, J., et al., "Adaptive Virtual Synchronous Control of SiC Grid-Forming Inverters Under Low Short-Circuit Ratios," *IEEE Transactions on Power Electronics*, vol. 39, no. 11, pp. 14201–14214, November 2024.

## Overview and Research Scope

This paper details the core control algorithms developed by Lumen Grid Labs, LLC under our NSF SBIR Phase I 2024 grant ("Grid-forming control for weak grids", $275,000). Research was conducted at our facility in Golden, Colorado, in collaboration with academic researchers at the Colorado School of Mines. The work tackles transient instability and voltage collapse in distribution networks characterized by low short-circuit ratios (SCR < 1.5) and high penetration of distributed energy resources.

## Experimental Configuration and Laboratory Setup

All experimental validation was performed inside our 1,800 sq ft power-electronics lab utilizing the following infrastructure:

- **Inverter Platform:** Lumen Grid Labs' HelioLink 250, a 250 kW SiC grid-forming inverter delivering 98.7% peak efficiency.
- **Grid Simulation:** A 500 kW regenerative grid simulator configured to emulate variable line impedances and frequency excursions.
- **Real-Time Simulation:** An OPAL-RT hardware-in-the-loop rig interfaced directly with the HelioLink 250 digital signal processing controller for millisecond-level hardware execution testing.

Dr. Maya Okafor (CEO) served as Principal Investigator, with hardware deployment led by Ravi Deshmukh (CTO) and rigorous bench testing executed by Jordan Lee (test engineer).

## Key Results and Performance Benchmarks

The journal publication outlines three central empirical findings from our hardware runs:

1. **Fault Ride-Through Performance:** The adaptive virtual impedance loop achieved a 14% faster fault ride-through than baseline droop-controlled architectures during asymmetrical phase-to-ground faults.
2. **Voltage Support in Weak Interconnections:** At an SCR of 1.2, the HelioLink 250 maintained steady-state terminal voltage within 1.0% of nominal without triggering overcurrent protections or requiring supplementary active damping hardware.
3. **Harmonic Suppression:** Total harmonic distortion (THD) of the injected current remained below 2.1% under severe grid background distortion, outperforming standard IEEE 1547 compliance requirements.

## Internal Impact and Next Steps

These published findings establish formal peer-reviewed validation for the HelioLink 250 platform. Moving forward, the algorithms will be integrated with field demonstration units supported by our utility partner, Front Range Utility Cooperative, following their 2025 letter of support. Additionally, battery scientist Elena Brandt is evaluating cross-platform integration between this control framework and the LGL-BMS3 solid-state battery management system (cell balancing ±2 mV, SoC estimation error ≤ 1.5%) to study DC-link stabilization under fast load steps.

*Internal Inquiries:* contact Dr. Maya Okafor (m.okafor@example.com / 555-0144) or Ravi Deshmukh (r.deshmukh@example.com / 555-0145).
