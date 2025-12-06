# JIRA: MBL-TEST-4242 — Modify Room Type from Reservation Detail (RLM)

## Preconditions / Flags
- Member has an upcoming reservation
- Quick Search FF = ON (CHACHING > SEARCH > Quick Search)
- Recipe C = ON (RLM enabled in AB Overrides)

## Scenario (happy path)
1) User is on Trips tab
2) Tap specific reservation → Stay page (Reservation Detail)
3) Tap room type link under Stay Information
4) Modal "Modify Your Reservation?" appears
5) Tap Continue → Room List (RLM)
6) Select a view rate type → Rate Type screen
7) Select any Rate type → Confirm Changes
8) Tap Book Now → booking completed → Reservation Confirmation shows modifications

## Negative
- Cancel at modal → remain on Reservation Detail; no changes.
