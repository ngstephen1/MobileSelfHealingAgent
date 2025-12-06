@enabled:true
@author:Synthetic
@regression @en_US @pilot_ai
@description:Verify_Modify_Room_Type_from_Reservation_Detail

Scenario: TC_APP_Synth_Modify_Room_Type
  When user opens "Trips" tab
  Then user verify "Trips" page
  When user taps on "currentReservation" button
  Then user verify "Stay" page
  When user taps on "stay.modify.link" button
  Then user sees "Modify Your Reservation?" modal
  When user taps on "btn.continue" button
  Then user verify "Room List" page
  When user selects "opt.viewRate" option
  Then user verify "Rate Type" page
  When user selects "rate.any" rate
  Then user verify "Confirm Changes" page
  When user taps on "btn.bookNow" button
  Then booking is completed
  And reservation confirmation screen shows "roomType" equals "rate.any"
