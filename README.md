# Registrator
Flask application for hosting web registration system for Amateur Radio Nets

ToDo:
+ login and password for all users
- control for submitted parameters
- S3 export export on each submit
+ Google Sheet export on each submit
- CF or TF for Github actions to place on single spot instance
+ Logic to switch to maintenance page when app is offline
+ admin page
+ admin change topic
- admin list Net checkins
- admin delete checkins
- admin flush checkins
+ Separate button for us callsigns, https://callook.info/ for US callsigns lookup
- check-in types: normal (?), silent/listening, for the count
+ netcontrol text, to admin page

Test it out:
`export QRZ_USER=N0CALL`
`export QRZ_PASSWORD=password`
`docker-compose up --build`

Current Admin password is hardcoded in `app.py` file (related to `docker-compose.yaml`). For cloud deployments will be replaced (by sed) for parameter value.
