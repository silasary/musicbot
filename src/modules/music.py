import asyncio
import random
import uuid
from urllib import parse

import aiohttp
import lavalink
from interactions import *
from interactions.api.events import *
from interactions_lavalink import Lavalink, Player
from interactions_lavalink.events import TrackStart
from lavalink import LoadResult
import csv

from spotify_loader import SearchSpotify
from spotify_api import Spotify
from config_loader import load_config
from utils.fancy_send import fancy_message

spotify = Spotify(client_id=load_config('api', 'spotify', 'id'), secret=load_config('api', 'spotify', 'secret'))
with open('src/SiIvaGunner Rips - SiIvaGunner.csv', 'r') as file:
    data = csv.reader(file)
    songs = [r[0] for r in data]

class Music(Extension):

    def __init__(self, client):
        self.client: Client = client
        self.lavalink: Lavalink | None = None

    async def queue_random(self, player: Player):
        if player.queue:
            print('Queue already has songs.')
            return
        s = random.choice(songs)
        result = await self.lavalink.client.get_tracks('https://www.youtube.com/watch?v=' + s, check_local=True)

        if not result.tracks:
            songs.pop(songs.index(s))
            return await self.queue_random(player)

        player.add(result.tracks[0], requester=self.client.user.id)

    @listen()
    async def on_ready(self):
        # Initializing lavalink instance on bot startup
        self.lavalink: Lavalink = Lavalink(self.client)

        node_information: dict = load_config('api', 'lavalink')

        # Connecting to local lavalink server
        self.lavalink.add_node(node_information['ip'], node_information['port'], node_information['password'], "us")

        self.lavalink.client.register_source(SearchSpotify())

        print("Music Command Loaded.")

        await self.update_rips()

    async def update_rips(self):
        with aiohttp.ClientSession() as session:
            rips = await session.get("https://docs.google.com/spreadsheets/d/1B7b9jEaWiqZI8Z8CzvFN1cBvLVYwjb5xzhWtrgs4anI/gviz/tq?tqx=out:csv&sheet=SiIvaGunner")
            content = await rips.text()
            with open('src/SiIvaGunner Rips - SiIvaGunner.csv', 'w') as file:
                file.write(content)

    @slash_command(description="Listen to music!")
    async def music(self, ctx: SlashContext):
        pass

    async def get_playing_embed(self, player_status: str, player: Player, allowed_control: bool):

        track = player.current

        if track is None:
            return
        
        bar_empty = '░'
        bar_filled = '█'

        progress_bar_length = 15
        current_time = round((player.position / track.duration) * progress_bar_length)

        progress_bar_l = []
        for i in range(progress_bar_length):

            if i < current_time:
                bar_fill = bar_filled
            else:
                bar_fill = bar_empty

            progress_bar_l.append(bar_fill)

        progress_bar = ''.join(progress_bar_l)

        current = lavalink.format_time(player.position)
        total = lavalink.format_time(track.duration)

        description = f'From **{track.author}**\n### {progress_bar}\n{current} • {total}'

        embed = Embed(title=track.title, description=description, url=track.uri, color=0x2B2D31)
        embed.set_author(name=player_status)
        embed.set_thumbnail(self.get_cover_image(track.identifier))

        requester = await self.client.fetch_user(track.requester)

        control_text = 'Everyone can control' if allowed_control else 'Currently has control'
        embed.set_footer(text=f'Requested by {requester.username}  ●  {control_text}', icon_url=requester.avatar_url)

        return embed

    async def get_queue_embed(self, player: Player, page: int):
        queue_list = ''

        queue = player.queue[(page * 10) - 10: (page * 10)]
        i = (page * 10) - 9

        for song in queue:
            title = song.title
            author = song.author
            requester = await self.bot.fetch_user(song.requester)

            req = requester.mention if requester else ""
            queue_list = f'{queue_list}**{i}**. ***{title}*** by {author} - {req}\n'

            i += 1

        track = player.current
        guild = await self.bot.fetch_guild(player.guild_id)

        time = 0

        for t in player.queue:
            time = time + t.duration / 1000

        hours = int(time / 3600)
        minutes = int((time % 3600) / 60)

        description = f'### Currently Playing:\n**{track.title}** from **{track.author}**\n\n*There are currently* ***{len(player.queue)}*** *songs in the queue.*\n*Approximately* ***{hours} hours*** and ***{minutes} minutes*** *left.*\n### Next Up...\n{queue_list}'

        queue_embed = Embed(description=description, color=0x2B2D31)
        
        icon = None
        
        if guild.icon is not None:
            icon = guild.icon.url

        queue_embed.set_author(name=f'Queue for {guild.name}', icon_url=icon)
        queue_embed.set_thumbnail(url=self.get_cover_image(track.identifier))
        queue_embed.set_footer(text='Use /music_queue remove to remove a track.\nUse /music_queue jump to jump to a track.')

        return queue_embed

    async def can_modify(self, player: Player, author: User, guild_id: Snowflake):
        if not player.current:
            return True

        requester_member: Member = await self.bot.fetch_member(player.current.requester, guild_id)

        voice_state = requester_member.voice

        if Permissions.MANAGE_CHANNELS in author.guild_permissions:
            return True

        if not voice_state or not voice_state.channel:
            return False

        if int(author.id) == player.current.requester:
            return True

        return False

    @music.subcommand(sub_cmd_description="Play a song!")
    @slash_option(name="song", description="Input a search term, or paste a link.", opt_type=OptionType.STRING, required=True, autocomplete=True)
    async def play(self, ctx: SlashContext, song: str):

        # Getting user's voice state
        voice_state = ctx.author.voice
        if not voice_state or not voice_state.channel:
            return await fancy_message(ctx, "You're not connected to a voice channel.", color=0xff0000,
                                       ephemeral=True)

        print(song)

        message = await fancy_message(ctx, f"Loading search results...")

        # Connecting to voice channel and getting player instance
        player = await self.lavalink.connect(voice_state.guild.id, voice_state.channel.id)

        result: LoadResult = await self.lavalink.client.get_tracks(song, check_local=True)  # type: ignore
        tracks = result.tracks

        if len(tracks) == 0:
            await message.delete()
            return await fancy_message(ctx, "No results found.", color=0xff0000, ephemeral=True)

        player.store('Channel', ctx.channel)

        [player.add(track, requester=int(ctx.author.id)) for track in tracks]

        await message.delete()
        if player.is_playing:
            add_to_queue_embed = self.added_to_playlist_embed(ctx, player, tracks[0])

            return await ctx.channel.send(embeds=add_to_queue_embed)
        else:
            await player.play()

    def added_to_playlist_embed(self, ctx: SlashContext, player: Player, track: lavalink.AudioTrack):
        add_to_queue_embed = Embed(
            title=track.title,
            url=track.uri,
            description=f'From **{track.author}**\n\nSuccessfully added to queue.',
            color=0x2B2D31
        )

        add_to_queue_embed.set_author(name='Requested by ' + ctx.author.user.username,
                                      icon_url=ctx.author.user.avatar_url)

        add_to_queue_embed.set_thumbnail(self.get_cover_image(track.identifier))
        add_to_queue_embed.set_footer(text='Was this a mistake? Run /music remove_last to quickly remove.')

        return add_to_queue_embed

    @music.subcommand(sub_cmd_description="Play a file!")
    @slash_option(name="file", description="Input a file to play.", opt_type=OptionType.ATTACHMENT, required=True)
    async def play_file(self, ctx: SlashContext, file: Attachment):

        # Getting user's voice state
        voice_state = ctx.author.voice

        if not voice_state or not voice_state.channel:
            return await fancy_message(ctx, "You're not connected to a voice channel.", color=0xff0000,
                                       ephemeral=True)

        message = await fancy_message(ctx, f"Loading search results...")

        player = await self.lavalink.connect(voice_state.guild.id, voice_state.channel.id)

        track: list[lavalink.AudioTrack] = await player.get_tracks(file.url)

        if len(track) == 0:
            return await fancy_message(ctx, "Attachment must either be a video or audio file.", color=0xff0000,
                                       ephemeral=True)

        track: lavalink.AudioTrack = track[0]

        track.title = file.filename
        track.uri = file.url
        track.identifier = file.url
        track.author = 'Uploaded File'
        track.requester = int(ctx.author.id)

        player.add(track)

        player.store('Channel', ctx.channel)

        await message.delete()

        if player.is_playing:
            add_to_queue_embed = self.added_to_playlist_embed(ctx, player, track)

            return await ctx.channel.send(embeds=add_to_queue_embed)

        await player.play()

    @music.subcommand(sub_cmd_description="Stop the music!")
    async def stop(self, ctx: SlashContext):

        player: Player = self.lavalink.get_player(ctx.guild_id)

        if player is None:
            return await fancy_message(ctx, "Player not found, try putting on some music!", color=0xff0000, ephemeral=True)

        player.current = None
        await self.lavalink.disconnect(ctx.guild_id)

        await fancy_message(ctx, f"{ctx.author.mention} has stopped the player.")

    @slash_command(description="Additional controls for the Queue!")
    async def music_queue(self, ctx: SlashContext):
        pass

    @music_queue.subcommand(sub_cmd_description="Jump to a song!")
    @slash_option(name="position", description="The position of the song you want to jump to.", opt_type=OptionType.INTEGER, required=True)
    async def jump(self, ctx: SlashContext, position: int):

        voice_state = ctx.author.voice
        if not voice_state or not voice_state.channel:
            return await fancy_message(ctx, "You're not connected to a voice channel.", color=0xff0000, ephemeral=True)

        player: Player = self.lavalink.get_player(ctx.guild_id)

        if player is None:
            return await fancy_message(ctx, "Player not found, try putting on some music!", color=0xff0000, ephemeral=True)

        if len(player.queue) == 0:
            return await fancy_message(ctx, "Queue is empty!", color=0xff0000, ephemeral=True)

        if position > len(player.queue) or position < 0:
            return await fancy_message(ctx, "Invalid position!", color=0xff0000, ephemeral=True)

        song = player.queue[position]

        if player.loop != 2:
            del player.queue[:position]
        else:
            del player.queue[position]
            player.queue.insert(0, song)

        await player.skip()

        await fancy_message(ctx, f'{ctx.user.mention} jumped to **{song.title}**!')

    @music_queue.subcommand(sub_cmd_description="Remove a song from the queue.")
    @slash_option(name="position", description="The position of the song you want to remove.", opt_type=OptionType.INTEGER, required=True)
    async def remove(self, ctx: SlashContext, position: int):

        voice_state = ctx.author.voice
        if not voice_state or not voice_state.channel:
            return await fancy_message(ctx, "You're not connected to a voice channel.", color=0xff0000,
                                       ephemeral=True)

        player: Player = self.lavalink.get_player(ctx.guild_id)

        if player is None:
            return await fancy_message(ctx, "Player not found, try putting on some music!", color=0xff0000,
                                       ephemeral=True)

        if len(player.queue) == 0:
            return await fancy_message(ctx, "Queue is empty!", color=0xff0000, ephemeral=True)

        if position > len(player.queue) or position < 0:
            return await fancy_message(ctx, "Invalid position!", color=0xff0000, ephemeral=True)

        song = player.queue[position]
        
        can_remove = self.can_modify(player, ctx.author, ctx.guild_id)
        
        if song.requester != ctx.author.id and not can_remove:
            return await fancy_message(ctx, "You can't remove this song!", color=0xff0000, ephemeral=True)

        del player.queue[position]

        await fancy_message(ctx, f'{ctx.user.mention} removed **{song.title}** from the queue.')

    @remove.autocomplete('position')
    async def autocomplete_remove(self, ctx: AutocompleteContext):

        input_text = ctx.input_text
        player: Player = self.lavalink.get_player(ctx.guild_id)

        if player is None:
            return await ctx.send([])

        show_first_results = False

        if input_text == '':
            show_first_results = True

        queue = []

        for i, item in enumerate(player.queue):
            queue.append(f"{i + 1}. {item.title}")

        choices = []

        for i, item in enumerate(queue):
            if show_first_results:
                choices.append({"name": item, "value": i})
            else:
                if input_text.lower() in item.lower():
                    choices.append({"name": item, "value": i})

        if len(choices) > 24:
            choices = choices[:24]

        await ctx.send(choices)

    @jump.autocomplete('position')
    async def autocomplete_jump(self, ctx: AutocompleteContext):

        input_text = ctx.input_text
        player: Player = self.lavalink.get_player(ctx.guild_id)

        if player is None:
            return await ctx.send([])

        show_first_results = False

        if input_text == '':
            show_first_results = True

        queue = []

        for i, item in enumerate(player.queue):
            queue.append(f"{i + 1}. {item.title}")

        choices = []

        for i, item in enumerate(queue):
            if show_first_results:
                choices.append({"name": item, "value": i})
            else:
                if input_text.lower() in item.lower():
                    choices.append({"name": item, "value": i})

        if len(choices) > 24:
            choices = choices[:24]

        await ctx.send(choices)

    async def load_spotify_search(self, content):
        search_: dict = await spotify.search(content, limit=25, type='track')

        if search_ == 'error':
            return (
                [
                    {
                        "Text": "An error occurred within the search.",
                        "URL": "ef9hur39fh3ehgurifjehiie"
                    }
                ]
            )

        tracks = []

        for result in search_['tracks']['items']:
            song_name = result['name']
            artists = result['artists'][0]
            url = result['id']

            if len(f'"{song_name}"\n - {artists["name"]}') > 99:
                continue

            tracks.append({"Text": f'"{song_name}"\n by {artists["name"]}', "URL": f'http://open.spotify.com/track/{url}'})

        return tracks

    @play.autocomplete('song')
    async def autocomplete(self, ctx: AutocompleteContext):

        text = ctx.input_text

        if not text:
            return await ctx.send([])

        raw_text = text

        if len(text) > 25:
            text = text[:25]

        items = await self.load_spotify_search(text)

        if 'https://youtu.be' in text or 'https://www.youtube.com' in text or 'https://m.youtube.com' in text:
            choices = [
                {"name": '🔗 Youtube URL', "value": raw_text}
            ]
        elif 'http://open.spotify.com/' in text or 'https://open.spotify.com/' in text:
            choices = [
                {"name": '🔗 Spotify URL', "value": raw_text}
            ]
        elif 'https://soundcloud.com' in text:
            choices = [
                {"name": '🔗 Soundcloud URL', "value": raw_text}
            ]
        else:
            choices = [
                {"name": item['Text'], "value": item['URL']} for item in items
            ]

        try:
            await ctx.send(choices)
        except:
            pass

    @music.subcommand(sub_cmd_description='Remove the most recent song from the queue added by you.')
    async def remove_last(self, ctx: SlashContext):
        player = self.lavalink.get_player(ctx.guild_id)

        if not player:
            return await fancy_message(ctx, 'An error occurred, please try again later.', ephemeral=True, color=0xff0000)

        if len(player.queue) == 0:
            return await fancy_message(ctx, 'No song in queue.', ephemeral=True, color=0xff0000)

        queue = player.queue[::-1]

        for track in queue:
            if track.requester == int(ctx.user.id):
                player.queue.remove(track)
                return await fancy_message(ctx, f'{ctx.user.mention} removed **{track.title}** from the queue.')

    @listen()
    async def on_track_start(self, event: TrackStart):

        player: Player = event.player

        channel: GuildText = player.fetch('Channel')

        await self.on_player(event.player, channel)

    @listen()
    async def voice_state_update(self, event: VoiceUserLeave):
        player: Player = self.lavalink.get_player(event.author.guild.id)

        if player is None:
            return

        if event.author.bot:
            return

        channel = event.channel

        if not channel.id == player.channel_id:
            return

        if len(channel.voice_members) <= 2:
            # text_channel = player.fetch('Channel')

            # await fancy_message(text_channel, f'Everyone has disconnected from {channel.mention}. To stop playing music, please use ``/music stop``.')
            await self.lavalink.disconnect(event.author.guild.id)

    @listen()
    async def voice_state_join(self, event: VoiceUserJoin):
        if event.author.bot:
            return
        if event.channel.name == "lofi beets":
            player = await self.lavalink.connect(event.channel.guild.id, event.channel.id)
            player.store('Channel', event.channel)
            await self.queue_random(player)
            if not player.is_playing:
                await player.play()

    @staticmethod
    def get_buttons():
        return [
            Button(
                style=ButtonStyle.BLUE,
                emoji=PartialEmoji(id=1019286929059086418),
                custom_id="queue",
                label="Queue"
            ),

            Button(
                style=ButtonStyle.BLUE,
                emoji=PartialEmoji(id=1019286926404091914),
                custom_id="loop",
                label="Loop Song"
            ),

            Button(
                style=ButtonStyle.BLUE,
                emoji=PartialEmoji(id=1019286927888883802),
                custom_id="playpause",
                label="Pause"
            ),

            Button(
                style=ButtonStyle.BLUE,
                emoji=PartialEmoji(id=1019286930296410133),
                custom_id="skip",
                label="Skip"
            )
        ]

    @staticmethod
    async def get_queue_buttons():
        options = [
            Button(
                style=ButtonStyle.RED,
                emoji=PartialEmoji(id=1031309494946385920),
                custom_id="left"
            ),

            Button(
                style=ButtonStyle.BLUE,
                emoji=PartialEmoji(id=1031309497706225814),
                custom_id="shuffle",
                label="Shuffle"
            ),
            Button(
                style=ButtonStyle.GREY,
                emoji=PartialEmoji(id=1019286926404091914),
                custom_id="loopqueue",
                label="Loop Queue"
            ),

            Button(
                style=ButtonStyle.RED,
                emoji=PartialEmoji(id=1031309496401793064),
                custom_id="right"
            )
        ]

        return options

    @staticmethod
    async def get_lyrics(track: lavalink.AudioTrack):

        parsed_title = parse.quote(f'{track.title} {track.author}')

        api_url = f'https://some-random-api.com/lyrics?title={parsed_title}'

        async with aiohttp.ClientSession() as lyricsSession:
            async with lyricsSession.get(api_url) as jsondata:
                lyrics: dict = await jsondata.json()

        if 'error' in lyrics.keys():
            return Embed(title=f'{track.title} Lyrics', description='No Lyrics found.', color=0xFF0000)

        lyrics = lyrics['lyrics']

        if len(lyrics) > 4080:
            song = f'{lyrics[:2080]}...\n\nGet the full lyrics [here.]({lyrics.url})'

        return Embed(title=f'{track.title} Lyrics', description=lyrics, color=0x2B2D31, footer=EmbedFooter(text=f'Lyrics provided by Some Random API'))

    async def on_player(self, player: Player, channel: GuildText):

        if player.loop == 1:
            return

        player_uid = str(uuid.uuid4())

        player.store('uid', player_uid)

        main_buttons = Music.get_buttons()
        
        player_state = 'Now Playing...'
        embed = await self.get_playing_embed(player_state, player, True)

        message = await channel.send(embed=embed, components=main_buttons)

        stopped_track = player.current

        while player.current is not None and player_uid == player.fetch('uid'):

                if player.loop == 1:
                    player_state = 'Now Looping...'
                    main_buttons[1].label = 'Stop Looping'
                    main_buttons[1].style = ButtonStyle.GREEN
                else:
                    main_buttons[1].label = 'Loop Song'
                    main_buttons[1].style = ButtonStyle.BLUE
                
                if player.paused:
                    player_state = 'Paused'
                    main_buttons[2].label = 'Resume'
                    main_buttons[2].style = ButtonStyle.GREEN
                else:
                    player_state = 'Now Playing...'
                    main_buttons[2].label = 'Pause'
                    main_buttons[2].style = ButtonStyle.BLUE

                user = await self.bot.fetch_member(player.current.requester, player.guild_id)

                can_control: bool = False

                voice_state = user.voice
                if not voice_state or not voice_state.channel:
                    can_control = True

                embed = await self.get_playing_embed(player_state, player, can_control)

                message = await message.edit(embed=embed, components=main_buttons)

                await asyncio.sleep(1)

        await self.queue_random(player)
        await player.play()
        return
    
        embed = Embed(
            title=stopped_track.title,
            url=stopped_track.uri,
            description=f'From **{stopped_track.author}**',
            color=0x696969
        )

        embed.set_author(name="Stopped Playing...")
        embed.set_thumbnail(self.get_cover_image(stopped_track.identifier))

        requester = await self.bot.fetch_user(stopped_track.requester)

        embed.set_footer(text='Requested by ' + requester.username, icon_url=requester.avatar_url)

        message = await message.edit(content='💤', embed=embed, components=[])

    @component_callback('queue', 'loop', 'playpause', 'skip', 'lyrics')
    async def buttons(self, ctx: ComponentContext):

        player: Player = self.lavalink.get_player(ctx.guild_id)

        if player is None:
            return

        if ctx.custom_id == 'queue':

            player.store("current_page", 1)

            if len(player.queue) < 1:
                return await fancy_message(ctx, 'No songs in queue, use ``/music play`` to add some!', ephemeral=True, color=0xff0000)

            embed = await self.get_queue_embed(player, 1)

            components = await Music.get_queue_buttons()
            return await ctx.send(embed=embed, components=components, ephemeral=True)

        if ctx.custom_id == 'lyrics':
            message = await fancy_message(ctx, f'Searching Lyrics for this track...', ephemeral=True)
            embed = await self.get_lyrics(player.current)
            return await ctx.edit(message, embed=embed)

        if not await self.can_modify(player, ctx.author, ctx.guild.id):
            await fancy_message(ctx, 'You cannot modify the player.', ephemeral=True, color=0xff0d13)
            return

        await ctx.defer(edit_origin=True)

        if ctx.custom_id == 'loop':
            if not player.loop:
                player.set_loop(1)
                msg = await fancy_message(ctx.channel, f'{ctx.author.mention} Started Looping.')
            else:
                player.set_loop(0)
                msg =await fancy_message(ctx.channel, f'{ctx.author.mention} Stopped Looping.')

        if ctx.custom_id == 'playpause':
            await player.set_pause(not player.paused)

            if player.paused:
                msg = await fancy_message(ctx.channel, f'{ctx.author.mention} Paused.')
            else:
                msg = await fancy_message(ctx.channel, f'{ctx.author.mention} Resumed.')

        if ctx.custom_id == 'skip':
            await player.skip()

            await fancy_message(ctx.channel, f'{ctx.author.mention} Skipped.')
            
        if msg is not None:
            await msg.delete(delay=5)

    @component_callback('shuffle', 'loopqueue', 'left', 'right')
    async def queue_buttons(self, ctx: ComponentContext):

        player: Player = self.lavalink.get_player(ctx.guild_id)

        page = player.fetch('current_page')

        if ctx.custom_id == 'left':
            if page == 1:
                page = 1
            else:
                page -= 1

        max_pages = (len(player.queue) + 9) // 10

        if ctx.custom_id == 'right':
            if page < max_pages:  # Only allow moving to the right if there are more pages to display
                page += 1

        player.store('current_page', page)

        message = None

        if ctx.custom_id == 'shuffle':
            random.shuffle(player.queue)
            message = await fancy_message(ctx.channel, f'{ctx.author.mention} Shuffled the Queue.')

        if ctx.custom_id == 'loopqueue':
            if player.loop == 2:
                player.set_loop(0)
                message = await fancy_message(ctx.channel, f'{ctx.author.mention} Stopped Looping the Queue.')
            else:
                player.set_loop(2)
                message = await fancy_message(ctx.channel, f'{ctx.author.mention} is Looping the Queue.')

        embed = await self.get_queue_embed(player, page)

        components = await Music.get_queue_buttons()
        await ctx.edit_origin(embed=embed, components=components)
        if message is not None:
            await asyncio.sleep(5)
            await message.delete()

    def get_cover_image(self, uid: str):
        if 'https://i.scdn.co/' in uid:
            return uid
        else:
            return f"https://img.youtube.com/vi/{uid}/hqdefault.jpg"