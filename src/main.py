from interactions import listen, Activity, ActivityType, Client
from interactions.api.events import Startup
from config_loader import load_config
from load_modules import load_modules
from typing import Union

print('Loading your bot up...')

activity_types = [None, ActivityType.PLAYING, ActivityType.LISTENING, ActivityType.WATCHING]
activity_id = load_config('bot_customization', 'activity_type')
activity_type: Union[ActivityType, None] = activity_types[activity_id]

activity = Activity(load_config('bot_customization', 'activity'), activity_type)

client = Client(activity=activity)
client.load_extension('interactions.ext.jurigged')

load_modules(client)

@listen(Startup)
async def on_start():
    print(f'{client.user.display_name} is now ready to use commands. ✅')
    
client.start(token=load_config('TOKEN'))
