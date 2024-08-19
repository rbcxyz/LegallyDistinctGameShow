Sample python app made to experiment with parsing livechat and using OBS websockets.
Just threw this together in a few hours with little to no background knowledge so I'm sure this could be done much better as well.

This app attempts to address the seemingly two main pain points in the Win or No Win stream:
1. Instead of requiring polls, the app will parse chat and provide a live updating on screen graphic of chat's votes with the click of a single button. 
2. Once voting is ended, scene transitions are automated to open the case with the highest vote, and then remove it from the selection scene afterwards.