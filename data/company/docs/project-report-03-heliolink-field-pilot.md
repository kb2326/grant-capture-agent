> Synthetic document for grant-capture-agent evaluation. All people, numbers and results are fictional.

# HelioLink 250 Field Pilot Report (2025)
## Front Range Utility Cooperative

### Summary

In 2025 Lumen Grid Labs installed one HelioLink 250 grid-forming inverter, rated 250 kW, on a rural distribution feeder operated by Front Range Utility Cooperative. The pilot lasted six weeks. The inverter was available 99.2% of the time and tripped once. The trip was traced to a settings error that has since been corrected. Front Range Utility Cooperative issued a letter of support for the company's future work after the pilot.

### Setup

The inverter was connected to a feeder segment with a short-circuit ratio of about 2.5, which is weak by the standards used in our earlier tests. A small battery bank and a solar array shared the DC side. Jordan Lee commissioned the system and monitored it remotely, with weekly site visits. The inverter ran the adaptive virtual impedance controller developed under the 2024 NSF award.

### Results

| Measure | Result |
|---|---|
| Duration | 6 weeks (42 days) |
| Availability | 99.2% |
| Unplanned trips | 1 |
| Peak efficiency observed | 98.6% |
| Voltage deviation during cloud transients | within 2% of nominal |

Availability was calculated as time connected and ready divided by total time, so the 0.8% not available is about eight hours.

### The one trip

On day 19, the inverter disconnected for about 5 hours after a voltage dip on the feeder caused by a recloser operation. The logs showed that the dip was within the ride-through capability of the controller, but the inverter's undervoltage protection setting was 0.85 per unit for 100 ms, which was stricter than the 0.2 per unit for 150 ms used in the test plan. The root cause was a protection setting carried over from a factory default and not updated to match the test plan. No hardware was damaged. We corrected the setting, added a commissioning checklist item that compares all protection settings with the approved plan, and the inverter did not trip again.

### Lessons learned

1. Protection settings must be reviewed against the utility's own ride-through requirements before energizing.
2. Remote monitoring gave early warning of dips, and weekly site visits were adequate.
3. Peak efficiency in the field was 0.1 point below the laboratory figure of 98.7%, which we attribute to higher ambient temperature.

### Next steps

We plan a longer pilot of at least six months, with a second inverter, and want to add testing under unbalanced faults.

### Operations during the pilot

The inverter was commissioned over three days. Day one covered inspection, torque checks and insulation tests. Day two covered low-power energization at 25 kW, and day three raised output to full rating in steps. Weekly visits were used to download high-resolution logs, check filter temperatures and review any alarms. Front Range Utility Cooperative operators had a direct line to Jordan Lee and could request a remote disconnect at any time. They did not need to use it.

### Feedback from the cooperative

Cooperative staff said that the voltage behavior during cloud passes was smoother than with the grid-following inverters on neighboring feeders. They also asked for a clearer display of protection settings, which we added to the operator screen. These comments will guide the next pilot.
