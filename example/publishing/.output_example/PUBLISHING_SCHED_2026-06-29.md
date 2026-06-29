
# Description


## Overview


### Purpose and Scope

Personal Scheduler is a cross-platform application designed to help individual users organize daily activities, manage tasks, and track personal commitments through time-based reminders.  
  
The application targets the following platforms:  
  
- **Mobile** — iOS 16+ and Android 12+  

- **Desktop** — Windows 11 and macOS 13 (Ventura) or later  

- **Web** — modern browsers (Chrome 110+, Firefox 112+, Safari 16+)  
  
The document covers system requirements for Personal Scheduler version 1.0. It is structured as follows:  
  
1. **Description** — purpose, target users, and app function overview with UI description.  

2. **Requirements** — functional and non-functional requirements traceable to stakeholder needs.  
  
This document is intended for use by the development team, QA engineers, and product stakeholders throughout the product lifecycle. All requirements use the prefix `SCHED-SRS`.  

### Target Users

Personal Scheduler is designed for individual adult users who need to coordinate personal and professional commitments. No technical expertise is required to operate the application; onboarding for a new user is expected to take under five minutes.  
  
The following user profiles are addressed by this specification:  
  
- **Professionals** managing overlapping work deadlines, meetings, and personal errands from a single device.  

- **Students** tracking assignment due dates, exam schedules, and extracurricular activities.  

- **Freelancers** coordinating multiple client projects with flexible, self-defined workflows.  

- **General users** who want a lightweight, privacy-first alternative to calendar platforms that require cloud account sign-up.  
  
For each profile, the primary value the application provides is:  
  
1. **Professionals** — a single unified view of work and personal time, reducing context-switching between separate tools.  

2. **Students** — deadline visibility across multiple courses with early reminder alerts.  

3. **Freelancers** — tag-based task organization that maps naturally to per-client or per-project workstreams.  

4. **General users** — full offline functionality with no mandatory account registration.  

## App Functions


### Function List

The high-level architecture of Personal Scheduler is shown in Figure 1. The application is structured into three core functional modules — Calendar, Tasks, and Reminders — backed by a local encrypted data store and an optional cloud synchronization service.  
  
Figure 1. Personal Scheduler — Application Architecture.  
  
![](C:/work/vaults/BRUD/attachments/pics/scheduler-architecture.png)  
  
The functions performed by Personal Scheduler are listed in Table 1.  
  
Table 1. Personal Scheduler Functions.  
  
| **Function ID** | **Function Name**            | **Module**   | **Description**                                                                  |  
| --------------- | ---------------------------- | ------------ | -------------------------------------------------------------------------------- |  
| F_CAL_001       | Display calendar views       | Calendar     | Show events in day, week, month, and agenda views                                |  
| F_CAL_002       | Create and edit events       | Calendar     | Create, modify, and delete one-time and recurring calendar events                |  
| F_CAL_003       | Import/export calendar data  | Calendar     | Support iCalendar (.ics) format for import and export of events                  |  
| F_TASK_001      | Create and organize tasks    | Tasks        | Create tasks with title, description, due date, priority, and tags               |  
| F_TASK_002      | Group tasks into lists       | Tasks        | Support multiple named task lists with drag-and-drop reordering                  |  
| F_TASK_003      | Mark tasks as complete       | Tasks        | Check off tasks; completed tasks are archived and searchable                     |  
| F_REM_001       | Schedule reminders           | Reminders    | Attach time-based reminders to events and tasks                                  |  
| F_REM_002       | Deliver push notifications   | Reminders    | Send on-device push notifications at the scheduled reminder time                 |  
| F_REM_003       | Snooze and dismiss reminders | Reminders    | Snooze a reminder for a configurable interval or dismiss it entirely             |  
| F_SYNC_001      | Synchronize data             | Sync         | Optionally sync all user data with a personal cloud account in real time         |  
| F_AUTH_001      | Authenticate users           | Security     | Support PIN, password, and biometric (fingerprint / Face ID) unlock              |  
| F_SEARCH_001    | Search events and tasks      | UI / Core    | Full-text search across all events, tasks, and notes                             |  

### User Interface Overview

The application presents a bottom navigation bar giving access to three primary sections:  
  
- **Calendar** — day, week, month, and agenda views; color-coded event blocks per category.  

- **Tasks** — named task lists with priority indicators, tags, and due-date badges.  

- **Reminders** — chronological feed of upcoming alerts with snooze and dismiss actions.  
  
A persistent floating action button (FAB) allows quick creation of a new event or task from any screen without navigating away from the current view.  
  
A new user completes the following onboarding steps on first launch:  
  
1. Choose a display name (used in notifications; no account required).  

2. Grant notification permissions when prompted by the OS dialog.  

3. Select a default reminder lead time (5 / 10 / 15 / 30 / 60 minutes).  

4. Optionally enable cloud sync by signing in with an existing account or creating one.  

5. Optionally import an existing `.ics` calendar file.  
  
After onboarding, the user lands on the Calendar month view for the current month. Settings — accessible via a gear icon — expose preferences for theme (light / dark / system), default reminder lead time, notification sound, and cloud sync configuration.  

# Requirements


## Functional Requirements


### Calendar and Event Management

The calendar module is the primary time-management surface of Personal Scheduler. It handles the creation, storage, display, and editing of time-bound entries called *events*. An event has at minimum a title and a start time; all other fields are optional.  
  
Recurring events follow the RFC 5545 (iCalendar) recurrence rule syntax to ensure interoperability with third-party calendar applications. Event instances are materialized in the local store only when the relevant time window is displayed or queried, to avoid unbounded storage growth.  
  
<req_table_spacing>

|           |       |
|-----------|-------|
| ID | SCHED-SRS-001 |
| ObjType | REQ |
| SoR | CAL-STK-001 |
| SFTY | N |
| Function | F_CAL_001 |


**Requirement:**
The application **shall** display events in day, week, month, and agenda views. The currently active view **shall** persist across application restarts.

  
<req_table_spacing>

|           |       |
|-----------|-------|
| ID | SCHED-SRS-002 |
| ObjType | REQ |
| SoR | CAL-STK-002 |
| SFTY | N |
| Function | F_CAL_002 |


**Requirement:**
The application **shall** allow a user to create a calendar event by specifying at minimum a title and a start date/time. End date/time, location, description, recurrence rule, and category **shall** be optional fields.

  
<req_table_spacing>

|           |       |
|-----------|-------|
| ID | SCHED-SRS-003 |
| ObjType | REQ |
| SoR | CAL-STK-003 |
| SFTY | N |
| Function | F_CAL_002 |


**Requirement:**
The application **shall** support recurring events defined by a recurrence rule conforming to RFC 5545, including DAILY, WEEKLY, MONTHLY, and YEARLY frequency values, with optional UNTIL and COUNT termination conditions.

  
When the user edits a single instance of a recurring event, the application must offer three choices: edit only this instance, edit this and all following instances, or edit all instances. This prevents accidental modification of the entire recurrence series.  
  
<req_table_spacing>

|           |       |
|-----------|-------|
| ID | SCHED-SRS-004 |
| ObjType | REQ |
| SoR | CAL-STK-004 |
| SFTY | N |
| Function | F_CAL_003 |


**Requirement:**
The application **shall** support import and export of calendar data in iCalendar (.ics) format as defined by RFC 5545. Imported events **shall** be merged into the existing calendar without duplicating events that already exist based on matching UID fields.


### Task Management

Tasks differ from calendar events in that they represent actionable items rather than time-blocked appointments. A task may have a due date but does not occupy a time slot on the calendar grid.  
  
Tasks are organized into named lists. The application provides one default list ("Inbox") that cannot be deleted or renamed. Priority levels are: **High**, **Normal** (default), and **Low**. Tags are free-form text labels; a single task may carry multiple tags.  
  
<req_table_spacing>

|           |       |
|-----------|-------|
| ID | SCHED-SRS-005 |
| ObjType | REQ |
| SoR | TASK-STK-001 |
| SFTY | N |
| Function | F_TASK_001 |


**Requirement:**
The application **shall** allow a user to create a task with the following attributes: title (required), description (optional), due date (optional), priority level (optional, default: Normal), and one or more tags (optional).

  
<req_table_spacing>

|           |       |
|-----------|-------|
| ID | SCHED-SRS-006 |
| ObjType | DER |
| SoR | TASK-STK-002 |
| SFTY | N |
| Function | F_TASK_002 |


**Requirement:**
The application **shall** allow users to create, rename, reorder, and delete task lists. Deleting a non-empty list **shall** require explicit confirmation and **shall** offer the user the choice to either move all contained tasks to the Inbox list or delete them permanently.

**Rationale:** Users allowed to create, rename, reorder, and delete task lists

**Comment:** For test purpose

  
<req_table_spacing>

|           |       |
|-----------|-------|
| ID | SCHED-SRS-007 |
| ObjType | DER |
| SoR | TASK-STK-003 |
| SFTY | N |
| Function | F_TASK_003 |


**Requirement:**
The application **shall** allow a user to mark a task as complete. Completed tasks **shall** be visually distinguished from pending tasks and moved to an archived view. The user **shall** be able to restore a completed task to pending status at any time.

**Rationale:** Users allowed to mark a task as complete

**Comment:** For test purpose

  
Subtasks are not in scope for version 1.0. The data model reserves a `parent_id` field to accommodate a parent-child task relationship in a future release; this field **shall not** be exposed in the version 1.0 user interface.  

### Reminders and Notifications

Reminders are time-triggered notifications attached to events or tasks. A single event or task may have multiple reminders. The default reminder lead time is configurable in settings; the factory default is 15 minutes before the item's start or due time.  
  
On mobile platforms, reminders are delivered as push notifications through the native OS notification system (APNs on iOS, FCM on Android). On desktop, system tray notifications are used. If the device is offline or the application is not running, the mobile OS notification daemon is responsible for queuing and delivering the notification when the device reconnects or the application relaunches.  
  
<req_table_spacing>

|           |       |
|-----------|-------|
| ID | SCHED-SRS-008 |
| ObjType | REQ |
| SoR | REM-STK-001 |
| SFTY | N |
| Function | F_REM_001 |


**Requirement:**
The application **shall** allow a user to attach one or more time-based reminders to any event or task. Each reminder **shall** be defined by an offset relative to the item's start time (for events) or due date/time (for tasks), expressed in minutes, hours, or days before the item.

  
<req_table_spacing>

|           |       |
|-----------|-------|
| ID | SCHED-SRS-009 |
| ObjType | REQ |
| SoR | REM-STK-002 |
| SFTY | N |
| Function | F_REM_002 |


**Requirement:**
The application **shall** deliver reminder notifications on the scheduled device even when the application is running in the background or is fully closed, using native OS notification scheduling APIs: UNUserNotificationCenter on iOS, AlarmManager on Android, and Windows Task Scheduler on Windows.

  
<req_table_spacing>

|           |       |
|-----------|-------|
| ID | SCHED-SRS-010 |
| ObjType | REQ |
| SoR | REM-STK-003 |
| SFTY | N |
| Function | F_REM_003 |


**Requirement:**
Each delivered reminder notification **shall** present at least two actions: **Snooze** and **Dismiss**. The snooze intervals available to the user **shall** be: 5, 10, 15, 30, and 60 minutes. The default snooze interval **shall** be configurable in application settings with a factory default of 10 minutes.

  
Notification permissions on mobile platforms must be requested from the user at the time of first reminder creation, not at install. If the user denies permissions, the application **shall** display an in-app banner with a direct link to the device settings. The application **shall** remain fully functional for users who do not grant notification permissions; only background delivery will be unavailable.  

## Non-Functional Requirements


### Performance and Usability

Performance requirements are defined to ensure the application remains responsive on mid-range hardware. The reference device for mobile targets is a smartphone released no more than four years prior to the version 1.0 release date, running the minimum supported OS version.  
  
Perceived responsiveness is more important than raw throughput for a scheduling application. Users interact in short bursts — creating an event, checking the agenda, dismissing a reminder — and each interaction must feel instantaneous.  
  
<req_table_spacing>

|           |       |
|-----------|-------|
| ID | SCHED-SRS-011 |
| ObjType | REQ |
| SoR | PERF-STK-001 |
| SFTY | N |
| Function | F_CAL_001 |


**Requirement:**
The application **shall** render the calendar month view, including all events for the displayed month, within 300 milliseconds of a navigation gesture on the reference device, measured from the moment the gesture is initiated to the moment the view is fully drawn and interactive.

  
<req_table_spacing>

|           |       |
|-----------|-------|
| ID | SCHED-SRS-012 |
| ObjType | REQ |
| SoR | PERF-STK-002 |
| SFTY | N |
| Function | F_SEARCH_001 |


**Requirement:**
Full-text search across all events and tasks **shall** return results within 500 milliseconds for a local dataset of up to 10,000 items. The search input field **shall** display a loading indicator if results are not available within 200 milliseconds of the last keystroke.

  
The application **shall not** consume more than 50 MB of RAM while idle on mobile platforms. Background processes related to reminder scheduling **shall** be limited to native OS scheduling APIs and **shall** not maintain a persistent background service process.  

### Data and Security

Personal Scheduler stores all user data in a local SQLite database on the device. The stored data types include:  
  
- Events (title, times, recurrence rules, category, location)  

- Tasks (title, description, due date, priority, tags)  

- Reminder configurations (offsets, snooze history)  

- Application settings and preferences  
  
The cloud synchronization feature is strictly opt-in. The application is fully functional without an account or network connectivity. This design choice is deliberate for two reasons:  
  
1. It reduces the attack surface by eliminating mandatory server-side data storage.  

2. It ensures that users sensitive about personal schedule data can keep it entirely on-device.  
  
When cloud sync is enabled, the following security measures apply:  
  
- Data is encrypted in transit using TLS 1.3 or higher.  

- The sync service does not receive or store decryption keys.  

- End-to-end encryption is implemented using a user account-derived key, so the sync service can relay but not read user data.  
  
<req_table_spacing>

|           |       |
|-----------|-------|
| ID | SCHED-SRS-013 |
| ObjType | REQ |
| SoR | SEC-STK-001 |
| SFTY | N |
| Function | F_AUTH_001 |


**Requirement:**
The application **shall** encrypt the local database at rest using AES-256 with a key derived from the user's device authentication credential (PIN, password, or biometric). The database **shall** be inaccessible without successful device authentication.

  
<req_table_spacing>

|           |       |
|-----------|-------|
| ID | SCHED-SRS-014 |
| ObjType | REQ |
| SoR | SEC-STK-002 |
| SFTY | N |
| Function | F_SYNC_001 |


**Requirement:**
When cloud synchronization is enabled, all data transmitted between the device and the sync service **shall** be encrypted end-to-end. The sync service **shall** receive only ciphertext. The encryption algorithm **shall** be XChaCha20-Poly1305 with a key derived from a user-controlled passphrase using Argon2id (minimum parameters: m=65536, t=3, p=4).

  
Data retention rules are as follows:  
  
1. If the user disables cloud sync or deletes their account, the sync service **shall** purge all stored ciphertext within 30 days.  

2. The application **shall** inform the user of this policy in the sync settings screen before the feature is activated.  

3. Local data on the device is never affected by account deletion and remains until the user explicitly clears application data through device settings.  