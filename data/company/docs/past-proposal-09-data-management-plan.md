> Synthetic document for grant-capture-agent evaluation. All people, numbers and results are fictional.

# Lumen Grid Labs: Data Management Plan (2025)

## 1. Overview and Purpose
Lumen Grid Labs, LLC (Golden, Colorado; founded 2019; 32 employees; 100% U.S.-owned; UEI LGLSYNTH0001) establishes this Data Management Plan to govern the collection, processing, preservation, and sharing of technical data generated across our research initiatives. This policy applies to research conducted internally and in coordination with our external partners, including the Colorado School of Mines (our STTR research partner) and Front Range Utility Cooperative (letter of support 2025).

## 2. Experimental Data Collection and Sources
All research activities are executed within our 1,800 sq ft power-electronics lab using specialized infrastructure, notably our 500 kW regenerative grid simulator and OPAL-RT hardware-in-the-loop rig. Data streams fall into two primary hardware domains:

1. **Battery Management Systems**: Supervised by Elena Brandt (lead battery scientist), datasets capture cell voltage telemetry, thermal logs, and degradation metrics for the LGL-BMS3 solid-state battery management system. Verification testing tracks cell balancing ±2 mV and SoC estimation error ≤ 1.5%, building on results from our DOE SBIR Phase I 2023 project ("Degradation-aware BMS for second-life batteries", $200,000; met all milestones).
2. **Inverter and Power Electronics**: Supervised by Ravi Deshmukh (CTO, power electronics) and Jordan Lee (test engineer), datasets capture time-domain waveform captures, thermal dissipation, and switching profiles for the HelioLink 250 250 kW SiC grid-forming inverter (98.7% peak efficiency). This infrastructure also records dynamic transient responses benchmarked against our NSF SBIR Phase I 2024 project ("Grid-forming control for weak grids", $275,000; 14% faster fault ride-through than baseline).

## 3. Data Storage, Formats, and Software Preservation
Raw time-series files are captured in open, machine-readable formats (CSV, HDF5, and Parquet) alongside MATLAB and Python configuration scripts. Firmware source code and FPGA bitstreams utilized during hardware-in-the-loop testing are version-controlled in Git repositories tagged with semantic release versions.

Primary copies are housed on local fault-tolerant network storage arrays in the lab with automated daily offsite differential backups. Access permissions are managed directly by project leads to safeguard proprietary topology designs and trade secrets.

## 4. Public Access and Dissemination
In accordance with federal public access mandates for projects led by Dr. Maya Okafor (CEO, PI on both awards), final anonymized datasets supporting peer-reviewed publications will be deposited in Zenodo. Data uploaded to Zenodo will be assigned a persistent Digital Object Identifier (DOI), licensed under Creative Commons Attribution (CC-BY 4.0), and retained for a minimum of ten years.

## 5. Contact Information
Questions regarding data access, software licensing, or technical protocols should be addressed to Dr. Maya Okafor at mokafor@example.com or 555-0128.
