> Synthetic document for grant-capture-agent evaluation. All people, numbers and results are fictional.

# Field Pilot Report: LGL-BMS3 Deployment with Summit Storage Partners

**Date:** February 14, 2025  
**Author:** Elena Brandt, Lead Battery Scientist  
**Contributors:** Jordan Lee (Test Engineer), Ravi Deshmukh (CTO), Dr. Maya Okafor (CEO)  
**Facility:** Lumen Grid Labs, LLC · Golden, Colorado (UEI: LGLSYNTH0001)  
**Contact:** elena.brandt@example.com | 555-0182  

## Executive Summary

During Q4 2024 and January 2025, Lumen Grid Labs deployed the LGL-BMS3 solid-state battery management system into an active field trial with Summit Storage Partners. The primary objective was to validate our state-of-charge (SoC) estimation algorithms and active cell balancing across heterogeneous automotive modules repurposed into stationary storage. Building upon foundational algorithms developed under our DOE SBIR Phase I 2023 award ("Degradation-aware BMS for second-life batteries", $200,000; met all milestones), this 60-day pilot evaluated a 250 kWh second-life pack operating under real-world utility peak-shaving cycles.

## Pilot Architecture and Benchmarking

Pre-deployment verification took place at our Golden facility within our 1,800 sq ft power-electronics lab. Utilizing our 500 kW regenerative grid simulator and OPAL-RT hardware-in-the-loop rig, our 32 employees prepared the integration interface alongside academic collaboration models from the Colorado School of Mines. The pilot installation coupled the 250 kWh second-life pack directly to a HelioLink 250 250 kW SiC grid-forming inverter operating at 98.7% peak efficiency.

Key configuration metrics:
- **Storage Unit:** 250 kWh second-life pack consisting of 14 series-connected EV battery modules.
- **Management Hardware:** Lumen Grid Labs LGL-BMS3 solid-state battery management system.
- **Power Conversion:** HelioLink 250 (250 kW rated power, SiC topology).
- **Field Host:** Summit Storage Partners commercial demonstration facility.

## Performance Results

The deployment subjected the pack to 120 full charge-discharge cycles simulating daily commercial peak mitigation for distribution networks, in line with grid use cases supported by Front Range Utility Cooperative.

1. **State-of-Charge Tracking:** Throughout all thermal swings and dynamic load steps, the LGL-BMS3 maintained a SoC estimation error ≤ 1.5%, matching bench observations.
2. **Cell Balancing Precision:** Across degraded cells exhibiting significant capacity dispersion (initial cell delta > 78 mV), the solid-state active balancing architecture achieved cell balancing ±2 mV within 35 minutes of float charge.
3. **Inverter Interoperability:** Integration with the HelioLink 250 inverter showed zero communication dropouts or thermal throttling events during continuous 200 kW discharge cycles.

## Operational Milestones and Next Steps

Lead Test Engineer Jordan Lee confirmed all data telemetry pipelines remained stable across 1,440 hours of continuous field logging. The project met every operational benchmark established with Summit Storage Partners, confirming that degraded automotive packs can be stabilized effectively using active solid-state control.

Lumen Grid Labs will continue data collection through Q2 2025 to monitor long-term impedance rise. Insights will feed into our ongoing grid-support controls and collaborative modeling with the Colorado School of Mines.
