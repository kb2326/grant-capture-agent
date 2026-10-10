> Synthetic document for grant-capture-agent evaluation. All people, numbers and results are fictional.

# DOE SBIR Phase II: Technical Approach for Degradation-Aware BMS in Second-Life Battery Packs

## 1. Executive Summary & Prior Progress

Lumen Grid Labs, LLC (Golden, Colorado; founded 2019; 32 employees; 100% U.S.-owned; UEI LGLSYNTH0001) submits this technical approach for its DOE SBIR Phase II project. This proposal builds directly on our successful DOE SBIR Phase I 2023 award, "Degradation-aware BMS for second-life batteries" ($200,000; met all milestones). The objective is to scale and validate an active degradation-mitigating battery management architecture for second-life stationary storage.

Principal Investigator Dr. Maya Okafor (CEO, PI on both awards) leads the project, coordinating efforts with Elena Brandt (lead battery scientist), Ravi Deshmukh (CTO, power electronics), and Jordan Lee (test engineer). The project integrates complementary grid-interaction models established under our NSF SBIR Phase I 2024 award, "Grid-forming control for weak grids" ($275,000; 14% faster fault ride-through than baseline).

## 2. Technical Architecture & Hardware Integration

The project leverages our core commercial hardware: the LGL-BMS3 solid-state battery management system (cell balancing ±2 mV, SoC estimation error ≤ 1.5%) and the HelioLink 250 250 kW SiC grid-forming inverter (98.7% peak efficiency). 

Second-life packs exhibit uneven internal resistance, varied capacity fade, and divergent thermal profiles. To overcome these challenges, Phase II will execute three core innovations:

1. **Dynamic Cell Rebalancing**: Deploying LGL-BMS3 active balancing algorithms to dynamically adjust string current, holding cell balancing to within ±2 mV during dynamic dispatch.
2. **Electrochemical Impedance Estimation**: Working alongside STTR research partner Colorado School of Mines to embed real-time state-of-health tracking onto edge processors, keeping SoC estimation error ≤ 1.5%.
3. **Inverter Coupling**: Interfacing pack telemetry with the HelioLink 250 to throttle instantaneous power discharge based on pack thermal and degradation limits.

## 3. Work Plan and Experimental Validation

All experimental validation will occur in our 1,800 sq ft power-electronics lab located in Golden, Colorado. Testing leverages our 500 kW regenerative grid simulator and OPAL-RT hardware-in-the-loop rig to emulate utility distribution conditions.

- **Task 1: Module Characterization & Grading (Months 1–6)**: Elena Brandt will screen retired automotive packs into balanced 50 kWh sub-strings.
- **Task 2: Accelerated Stress Testing (Months 7–16)**: Jordan Lee will subject twelve prototype sub-strings to a rigorous 1,000-cycle accelerated aging protocol across temperature ranges from 15°C to 45°C. Degradation curves will validate active capacity preservation.
- **Task 3: Hardware-in-the-Loop Validation (Months 14–20)**: Ravi Deshmukh will connect the LGL-BMS3 and HelioLink 250 to the OPAL-RT hardware-in-the-loop rig and the 500 kW regenerative grid simulator, verifying seamless frequency response.
- **Task 4: Utility Demonstration Setup (Months 19–24)**: In collaboration with Front Range Utility Cooperative (letter of support 2025), Lumen Grid Labs will deploy a 250 kW / 500 kWh prototype at a cooperative substation site.

## 4. Key Project Personnel & Contact Information

- **Dr. Maya Okafor**, Principal Investigator: maya.okafor@example.com | 555-0120
- **Ravi Deshmukh**, CTO: ravi.deshmukh@example.com | 555-0121
- **Elena Brandt**, Lead Battery Scientist: elena.brandt@example.com | 555-0122
- **Jordan Lee**, Test Engineer: jordan.lee@example.com | 555-0123
