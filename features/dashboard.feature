Feature: ADHD Dashboard Task Parsing
  As a user with executive function needs
  I want to parse a plain-text task list with ASCII shorthands
  So that tasks are categorized by schedule strength, quick effort, waiting gaps, and clusters

  Scenario: Categorize tasks with dates and standalone wait tags
    Given a task file exists with the following content:
      """
      ! 10:30 - 11:00 Weekly Sync @admin #30-min
      * Dry Whites @home #wait
      * Put away laundry @home #focus
      ? 10/4 4:30 Visit Comcast to switch bill @logistics #focus
      """
    When I process the task file
    Then I should identify 1 strongly scheduled task
    And I should identify 1 arbitrarily scheduled task with time "10/4 4:30"
    And I should find 1 gap filler task for standalone wait

  Scenario: Parse tasks with nested subtask breakdowns
    Given a task file exists with the following content:
      """
      ! 10:30 - 11:00 Weekly Sync @admin #30-min
      * 6 guitar net 2 pieces @skill-building
          * When I get to the Border vs Who Wants To Lives Forever
          * Whats Up vs Wedding Song, The
          * We Sing Hallelujah vs Uncle John's Band
      """
    When I process the task file
    Then the task "6 guitar net 2 pieces" should have 3 subtasks

  Scenario: Trigger dashboard refresh on file modification
    Given a task file exists with the following content:
      """
      ! 09:00 Standup @work
      """
    When the task file is updated with new tasks
    Then the task handler should parse 2 tasks