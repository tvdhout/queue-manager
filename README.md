# queue-manager
Discord bot to manage queue(s) of questions.

[Invite to server](https://discord.com/api/oauth2/authorize?client_id=801804229819891712&permissions=75840&scope=bot)

#### Enter setup with `?help`

### Help
##### Setup
This bot is used to manage a queue of questions and archive them when answered. This bot requires a small setup to be functional. You must set the channel in which to archive messages, the channels which are treated as queues, and the roles that can manage queues. See below on how to declare these.
##### Command usage
`?help` → Show this menu.
`?archive` → Use this command in the channel you want to use as archive.
`?queue #channels` → Declare channels as queues. You can tag one or multiple channels: `?queue #channel` / `?queue #channel1 #channel2 ...`
`?roles` → Declare roles as queue managers. You can tag one or multiple roles: `?roles @Role` / `?roles @Role1 @Role2 ...`
##### Queue management
When a regular user sends a message in a queue channel, the bot wil reply with :inbox_tray:. Consecutive messages by the same user (ignoring interruptions by managers) are regarded as one. A queue manager can click on the :inbox_tray: reaction to claim the question. Once answered it can be archived by clicking on the :outbox_tray:. Queue managers that are not the claimer of a question can still archive it, after clicking on the :white_check_mark: for confirmation, to avoid accidentally archiving a message you did not claim.

### Database schemas:

table `servers`:
| Column    | Type         | Null | Key     | Default |
|-----------|--------------|------|---------|---------|
| serverid  | VARCHAR(50)  | NO   | PRIMARY | NULL    |
| archiveid | VARCHAR(50)  | YES  |         | NULL    |
| queues    | VARCHAR(500) | YES  |         | NULL    |
| roles     | VARCHAR(500) | YES  |         | NULL    |

table `messages`:
| Column    | Type        | Null | Key     | Default |
|-----------|-------------|------|---------|---------|
| messageid | VARCHAR(50) | NO   | PRIMARY | NULL    |
| ownerid   | VARCHAR(50) | YES  |         | NULL    |
