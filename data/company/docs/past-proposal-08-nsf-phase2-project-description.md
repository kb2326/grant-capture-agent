> Synthetic document for grant-capture-agent evaluation. All people, numbers and results are fictional.

# NSF SBIR Phase II: Advanced Grid-Forming Control for Dead-Feeder Restoration

## 1. Executive Summary and Company Overview
Lumen Grid Labs, LLC (Golden, Colorado, founded 2019, 32 employees, 100% U.S.-owned, UEI LGLSYNTH0001) submits this NSF SBIR Phase II project description to scale and validate autonomous grid-forming controls for distribution systems. Under the leadership of Dr. Maya Okafor (CEO, PI on both awards) and Ravi Deshmukh (CTO, power electronics), Lumen Grid Labs manufactures cutting-edge power systems. Our core commercial offerings include the LGL-BMS3 solid-state battery management system (cell balancing ±2 mV, SoC estimation error ≤ 1.5%) and the HelioLink 250 250 kW SiC grid-forming inverter (98.7% peak efficiency).

## 2. Prior Phase I Accomplishments
This project directly builds on the technical breakthroughs achieved under NSF SBIR Phase I 2024, "Grid-forming control for weak grids" ($275,000; 14% faster fault ride-through than baseline). In Phase I, we implemented a virtual synchronous machine control architecture that maintained stability under extreme grid-impedance variations. Complemented by our successful completion of DOE SBIR Phase I 2023, "Degradation-aware BMS for second-life batteries" ($200,000; met all milestones), our technical team proved that combining high-speed power conversion with precision battery monitoring creates an exceptionally stable foundation for low-inertia distribution networks.

## 3. Phase II Technical Scope: Restoring a Dead Feeder
The primary objective of this Phase II effort is extending our grid-forming inverter algorithms to enable robust black-start capability for disconnected distribution infrastructure. Restoring a dead feeder requires seamless voltage ramp-up and load energization without relying on external reference signals from a bulk transmission network.

Key research and development objectives include:
- Developing decentralized voltage-building algorithms that ramp unenergized 12.47 kV distribution lines to nominal voltage within 3.5 seconds while mitigating transformer inrush currents.
- Coordinating parallel HelioLink 250 units to share real and reactive power evenly during step changes, using active droop controls.
- Integrating the inverter controls directly with the LGL-BMS3 platform to maintain safe operational limits during heavy cold-load pickup transients.

## 4. Facilities, Verification, and Key Partnerships
Experimental evaluation will be conducted inside our dedicated 1,800 sq ft power-electronics lab. The research team will utilize our 500 kW regenerative grid simulator and our OPAL-RT hardware-in-the-loop rig to simulate full feeder dynamics under severe fault conditions. Lead battery scientist Elena Brandt will direct battery-pack dynamics and state estimation during high-power discharges, while test engineer Jordan Lee will execute hardware-in-the-loop simulations and power-stage validation.

To ensure utility readiness, Lumen Grid Labs has partnered with Colorado School of Mines (STTR research partner) for advanced dynamic stability modeling, and Front Range Utility Cooperative (letter of support 2025) to provide real-world feeder network topologies and load profiles for pilot simulation.

**Contact:** Dr. Maya Okafor, PI | maya.okafor@example.com | 555-0144
