# queue-manager
Discord bot to manage queue(s) of questions.

[Invite to server](https://discord.com/api/oauth2/authorize?client_id=801804229819891712&permissions=75840&scope=bot)

Enter setup with `?help`

Database schemas:

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
