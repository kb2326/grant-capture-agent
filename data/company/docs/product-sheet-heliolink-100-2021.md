> Synthetic document for grant-capture-agent evaluation. All people, numbers and results are fictional.

# HelioLink 100 Product Specification Sheet (2021)

**Release Date:** November 12, 2021  
**Document Status:** Legacy Product Datasheet  
**Manufacturer:** Lumen Grid Labs, LLC — Golden, Colorado  

## Overview

The HelioLink 100 is a 100 kW grid-tied solar and energy storage inverter developed by Lumen Grid Labs. Engineered at our Golden, Colorado facility during our second year of operation following our founding in 2019, the unit serves commercial and industrial scale power conversion needs. As the predecessor to our higher-capacity platforms, the HelioLink 100 established our core digital inverter control loops and thermal management strategies.

## Technical Specifications

- **Continuous Rated AC Output:** 100 kW
- **Peak Efficiency:** 96.5% peak efficiency
- **CEC Weighted Efficiency:** 95.8%
- **Nominal Grid Voltage:** 480 VAC, 3-phase, 4-wire
- **Nominal Frequency:** 60 Hz (57.0–63.0 Hz operating window)
- **Total Harmonic Distortion (THD):** < 3.0% at rated power
- **Power Factor Range:** 0.8 leading to 0.8 lagging (adjustable)
- **DC Bus Operating Range:** 550 VDC to 950 VDC
- **Maximum DC Input Voltage:** 1,000 VDC
- **Semiconductor Topology:** Silicon IGBT dual-bridge topology switching at 16 kHz
- **Enclosure:** NEMA 4X / IP66 rated for outdoor mounting
- **Cooling:** Forced air with redundant variable-speed brushless fans
- **Operating Temperature Range:** -25°C to +50°C (linear derating above 40°C)

## Control and Functional Architecture

The HelioLink 100 features a dedicated digital signal processing (DSP) architecture providing real-time current regulation and voltage synchronization. Key operational features include:
- Voltage and frequency disturbance ride-through compliance per IEEE 1547-2018 standards
- Autonomous power curtailment during over-frequency events
- High-speed active anti-islanding protection with disconnect trigger in under 80 ms
- Modbus RTU interface over RS-485 for telemetry and power curtailment dispatching

## Laboratory Verification

Performance validation of the HelioLink 100 was carried out in our 1,800 sq ft power-electronics lab. Chief Technology Officer Ravi Deshmukh and test engineer Jordan Lee executed over 600 hours of continuous thermal and electrical load cycling. The testing protocol used our 500 kW regenerative grid simulator alongside an OPAL-RT hardware-in-the-loop rig to simulate severe grid voltage sags and phase imbalances. Throughout characterization, the power stage demonstrated stable control margins and confirmed the target 96.5% peak efficiency rating across high-irradiance operational bands.

*Notice: The HelioLink 100 has been discontinued for new production runs. Lumen Grid Labs maintains field maintenance support and spare components for all existing utility and commercial installations.*

## Contact Information

For technical documentation, replacement parts, or service inquiries regarding legacy HelioLink hardware:

- **Customer Service:** support@example.com  
- **Technical Inquiries:** info@example.com  
- **Phone:** (303) 555-0144  
- **Headquarters:** Lumen Grid Labs, LLC, Golden, Colorado
