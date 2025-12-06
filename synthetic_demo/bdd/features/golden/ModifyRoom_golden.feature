@enabled:true
@author:QE
@regression @en_US
@description:Modify_room_type_from_reservation_detail

Scenario: Golden_Modify_Room
  When user opens "Trips" tab
  Then user verify "Trips" page
  When user taps on "currentReservation" button
  Then user verify "Stay" page
  When user taps on "modifyReservation" button
  Then user sees "Modify Your Reservation?" modal
  When user taps on "Continue" button
  Then user verify "Room List" page
  When user selects "viewRate" option
  Then user verify "Rate Type" page
  When user selects "Flexible" rate
  Then user verify "Confirm Changes" page
  When user taps on "Book Now" button
  Then booking is completed
  And reservation confirmation screen shows "roomType" equals "Flexible"
