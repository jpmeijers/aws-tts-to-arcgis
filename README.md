# Readme

## Deploy to AWS

Install aws-cli: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html

Set up aws-cli: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-quickstart.html

Build and deploy:
```
sam build
sam deploy --resolve-image-repos
```
Note the URL that is printed at the end of the deploy process. This is the URL we need to use on TTS.

Remove stack:
```
sam delete
```

## Configure webhook on The Things Stack

You need the URL that was printed at the end of the `sam deploy` step. Otherwise you need to log into the AWS Console, brose to Lambda functions, and not the trigger URL for the ingress lambda function.

On TTS Console, go to the application containing the device that needs to be forwarded to ArcGis. Select API Keys.
* Add API Key
* Give it any name
* Don't set an expiry date
* Grant individual rights
* Choose:
    * View devices in application
    * View application information
    * Write downlink application traffic
    * Read application traffic
* Copy the key value and save it in a safe spot for later.

On TTS Console, go to the application containing the device that needs to be forwarded to ArcGis. Select Integrations, Webhooks, Add Webhook, Custom Webhook.

* Webhook ID: tts-to-arcgis
* Webhook Format: JSON
* Base URL: The URL from the sam deploy step.
* Downlink API Key: Paste the value you copied in the previous section.
* Under Enabled Event Types select Uplink Message
* Click Add Webhook

## Add device attributes

Choose the device that needs to be forwarded to ArcGis. Go to the general tab.

Under Attributes add 4 new fields:
* `arcgis-client-id`: You need to create a new application on ArcGis. This is the application's ID.
* `arcgis-client-secret`: The ArcGis application's secret.
* `arcgis-item-id-history`: A feature layer item ID where a full history of value will be appended. 
* `arcgis-item-id-last`: A feature layer item ID where the last received message will be updated to. 