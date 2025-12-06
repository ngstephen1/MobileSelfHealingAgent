### TC_APP_UpdateReservation.feature
@regression @pilot_ai @en_US @jira=MBL-TEST-4242
Feature: Update reservation: change to Deluxe King with price guardrails and fallback
  As a Marriott Bonvoy member
  I want to modify my room type to Deluxe King with price considerations
  So that I can ensure my preferred room is secured within acceptable rate limits

  Background:
    Given user enables feature flag "quickSearch"
    And user enables feature flag "recipeC"
    And user signs in as "memberWithUpcomingReservation"

  @description:Verify updating room type to Deluxe King with different rate selections, implicitly handling price guardrails.
  Scenario Outline: Update Room Type to Deluxe King with Rate Selection
    When user opens "Trips" tab
    Then user verify "Trips" page
    When user taps on "currentReservation" button
    Then user verify "Stay" page
    When user taps on "stay.modify.link" button
    Then user sees "Modify Your Reservation?" modal
    When user taps on "btn.continue" button
    Then user verify "Room List" page
    When user selects "room.deluxeKing" option
    Then user verify "Rate Type" page
    When user selects "<rateType>" rate
    Then user verify "Confirm Changes" page
    When user taps on "btn.bookNow" button
    Then booking is completed
    And reservation confirmation screen shows "roomType" equals "Deluxe King"

    Examples:
      | rateType           |
      | rate.bestAvailable |
      | rate.memberRate    |