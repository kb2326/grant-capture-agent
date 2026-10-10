> Synthetic document for grant-capture-agent evaluation. All people, numbers and results are fictional.

# Hardware-in-the-Loop Validation Report: HelioLink 250 Grid-Forming Controls

**Author:** Jordan Lee, Test Engineer  
**Reviewed By:** Ravi Deshmukh, CTO; Dr. Maya Okafor, CEO  
**Facility:** Lumen Grid Labs, LLC · Golden, Colorado  
**Date:** February 14, 2025  
**Contact:** jlee@example.com | 555-0142  

## 1. Executive Summary

Lumen Grid Labs, LLC (Golden, Colorado; founded 2019; 32 employees; 100% U.S.-owned; UEI LGLSYNTH0001) completed a hardware-in-the-loop (HIL) testing campaign validating advanced grid-forming control algorithms for the HelioLink 250. The HelioLink 250 is a 250 kW SiC grid-forming inverter designed for weak-grid environments, featuring a 98.7% peak efficiency. This validation builds directly upon findings from our NSF SBIR Phase I 2024 award, "Grid-forming control for weak grids" ($275,000), which achieved 14% faster fault ride-through than baseline benchmarks. The test run was executed to verify performance under high-stress distribution dynamics prior to field demonstration with our utility partner, Front Range Utility Cooperative.

## 2. Laboratory Setup and Test Configuration

All testing took place inside our dedicated 1,800 sq ft power-electronics lab. The physical and simulated testbed comprised:

- **Real-Time Simulation Platform:** OPAL-RT real-time digital simulator executing EMT-grade models of IEEE 33-bus weak distribution feeders at a 25-microsecond step time.
- **Power Hardware:** 500 kW regenerative grid simulator coupled with actual HelioLink 250 digital control boards running the proprietary virtual synchronous machine (VSM) firmware.
- **Interfacing:** High-speed analog and digital I/O connecting the OPAL-RT chassis directly to the inverter controller interface, alongside Colorado School of Mines research interface protocols.
- **Energy Storage Interface:** Integration emulation compatible with our LGL-BMS3 solid-state battery management system (cell balancing ±2 mV, SoC estimation error ≤ 1.5%).

## 3. Test Campaign and Findings

The evaluation matrix subjected the HelioLink 250 control hardware to 1,200 fault scenarios across variable grid conditions, including low short-circuit ratios (SCR from 1.1 to 2.5), phase-to-ground faults, three-phase symmetrical faults, and severe frequency dips (up to 2.5 Hz/s RoCoF).

Key quantitative outcomes include:

- **Fault Ride-Through Performance:** Across all 1,200 fault scenarios, the controller successfully maintained voltage source behavior without tripping or losing synchronism, reproducing the targeted 14% faster fault ride-through recovery time measured during the NSF Phase I campaign.
- **Dynamic Voltage Regulation:** Voltage support at the simulated point of common coupling settled within ±1.0% of nominal in less than 65 ms following fault clearance.
- **Frequency Response:** Active power response to sudden load step-changes (up to 150 kW) demonstrated robust synthetic inertia damping with zero oscillatory overshoot.

## 4. Next Steps

With OPAL-RT testing concluded and milestones achieved, Dr. Maya Okafor and Ravi Deshmukh have authorized controller release v2.4. Results are being shared with Front Range Utility Cooperative per their 2025 letter of support to prepare for scheduled site integration testing.
