import asyncio
import functools
import itertools
import math
import random
import discord
import youtube_dl
from async_timeout import timeout
from discord.ext import commands
import youtube_dl.utils
import dbkrpy
from yaml import load, dump
import yaml
from discord.utils import find
import time
from flask import Flask
from threading import Thread
import koreanbots
import light_koreanbots as lkb
from koreanbots.integrations.discord import DiscordpyKoreanbots
import DBSkr
import logging

logger = logging.getLogger('DBSkr')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('[%(asctime)s] [%(filename)s] [%(name)s:%(module)s] [%(levelname)s]: %(message)s'))
logger.addHandler(handler)

youtube_dl.utils.bug_reports_message = lambda: ''


class VoiceError(Exception):
    pass


class YTDLError(Exception):
    pass


class YTDLSource(discord.PCMVolumeTransformer):
    YTDL_OPTIONS = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'audioformat': 'mp3',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0',
    }

    FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
    }

    ytdl = youtube_dl.YoutubeDL(YTDL_OPTIONS)
    ytdl.cache.remove()

    def __init__(self, ctx: commands.Context, source: discord.FFmpegPCMAudio, *, data: dict, volume: float = 0.5):
        super().__init__(source, volume)

        self.requester = ctx.author
        self.channel = ctx.channel
        self.data = data

        self.uploader = data.get('uploader')
        self.uploader_url = data.get('uploader_url')
        date = data.get('upload_date')
        self.upload_date = date[6:8] + '.' + date[4:6] + '.' + date[0:4]
        self.title = data.get('title')
        self.thumbnail = data.get('thumbnail')
        self.description = data.get('description')
        self.duration = self.parse_duration(int(data.get('duration')))
        self.tags = data.get('tags')
        self.url = data.get('webpage_url')
        self.views = data.get('view_count')
        self.likes = data.get('like_count')
        self.dislikes = data.get('dislike_count')
        self.stream_url = data.get('url')

    def __str__(self):
        return '**{0.title}** by **{0.uploader}**'.format(self)

    @classmethod
    async def create_source(cls, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None):
        loop = loop or asyncio.get_event_loop()

        partial = functools.partial(cls.ytdl.extract_info, search, download=False, process=False)
        data = await loop.run_in_executor(None, partial)

        if data is None:
            raise YTDLError('Couldn\'t find anything that matches `{}`'.format(search))

        if 'entries' not in data:
            process_info = data
        else:
            process_info = None
            for entry in data['entries']:
                if entry:
                    process_info = entry
                    break

            if process_info is None:
                raise YTDLError('Couldn\'t find anything that matches `{}`'.format(search))

        webpage_url = process_info['webpage_url']
        partial = functools.partial(cls.ytdl.extract_info, webpage_url, download=False)
        processed_info = await loop.run_in_executor(None, partial)

        if processed_info is None:
            raise YTDLError('Couldn\'t fetch `{}`'.format(webpage_url))

        if 'entries' not in processed_info:
            info = processed_info
        else:
            info = None
            while info is None:
                try:
                    info = processed_info['entries'].pop(0)
                except IndexError:
                    raise YTDLError('Couldn\'t retrieve any matches for `{}`'.format(webpage_url))

        return cls(ctx, discord.FFmpegPCMAudio(info['url'], **cls.FFMPEG_OPTIONS), data=info)

    @classmethod
    async def search_source(self, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None):
        self.bot = bot
        channel = ctx.channel
        loop = loop or asyncio.get_event_loop()

        self.search_query = '%s%s:%s' % ('ytsearch', 10, ''.join(search))

        partial = functools.partial(self.ytdl.extract_info, self.search_query, download=False, process=False)
        info = await loop.run_in_executor(None, partial)

        self.search = {}
        self.search["title"] = f'**{search}**\n검색 결과입니다.'
        self.search["type"] = 'rich'
        self.search["color"] = 7506394
        self.search["author"] = {'name': f'{ctx.author.name}', 'url': f'{ctx.author.avatar_url}',
                                'icon_url': f'{ctx.author.avatar_url}'}

        lst = []
        count = 0
        e_list = []
        for e in info['entries']:
            # lst.append(f'`{info["entries"].index(e) + 1}.` {e.get("title")} **[{YTDLSource.parse_duration(int(e.get("duration")))}]**\n')
            VId = e.get('id')
            VUrl = 'https://www.youtube.com/watch?v=%s' % (VId)
            lst.append(f'`{count + 1}.` [{e.get("title")}]({VUrl})\n')
            count += 1
            e_list.append(e)

        lst.append('\n**번호를 입력하여 골라주세요! "취소" 를 입력하여 명령어를 취소할 수 있습니다.**')
        self.search["description"] = "\n".join(lst)

        em = discord.Embed.from_dict(self.search)
        await ctx.send(embed=em, delete_after=45.0)

        def check(msg):
            return msg.content.isdigit() == True and msg.channel == channel or msg.content == '취소' or msg.content == '취소'

        try:
            m = await self.bot.wait_for('message', check=check, timeout=45.0)

        except asyncio.TimeoutError:
            rtrn = 'timeout'

        else:
            if m.content.isdigit() == True:
                sel = int(m.content)
                if 0 < sel <= 10:
                    for key, value in info.items():
                        if key == 'entries':
                            """data = value[sel - 1]"""
                            VId = e_list[sel-1]['id']
                            VUrl = 'https://www.youtube.com/watch?v=%s' % (VId)
                            partial = functools.partial(self.ytdl.extract_info, VUrl, download=False)
                            data = await loop.run_in_executor(None, partial)
                    rtrn = self(ctx, discord.FFmpegPCMAudio(data['url'], **self.FFMPEG_OPTIONS), data=data)
                else:
                    rtrn = 'sel_invalid'
            elif m.content == '취소':
                rtrn = 'cancel'
            else:
                rtrn = 'sel_invalid'

        return rtrn

    @staticmethod
    def parse_duration(duration: int):
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        duration = []
        if days > 0:
            duration.append('{} days'.format(days))
        if hours > 0:
            duration.append('{} hours'.format(hours))
        if minutes > 0:
            duration.append('{} minutes'.format(minutes))
        if seconds > 0:
            duration.append('{} seconds'.format(seconds))

        return ', '.join(duration)


class Song:
    __slots__ = ('source', 'requester')

    def __init__(self, source: YTDLSource):
        self.source = source
        self.requester = source.requester

    def create_embed(self):
        embed = (discord.Embed(title='음악 링크', url="{0.source.url}".format(self),
                               description='```css\n{0.source.title}를(을) 재생하고 있어요.```'.format(self),
                               color=discord.Color.lighter_gray())
                 .set_author(name="음악을 재생하고 있어요.", url="", icon_url="https://musicnplanet.xyz/giphy.gif")
                 .add_field(name='요청자', value=self.requester.mention)
                 .set_thumbnail(url=self.source.thumbnail))
        return embed


class SongQueue(asyncio.Queue):
    def __getitem__(self, item):
        if isinstance(item, slice):
            return list(itertools.islice(self._queue, item.start, item.stop, item.step))
        else:
            return self._queue[item]

    def __iter__(self):
        return self._queue.__iter__()

    def __len__(self):
        return self.qsize()

    def clear(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)

    def remove(self, index: int):
        del self._queue[index]


class VoiceState:
    def __init__(self, bot: commands.Bot, ctx: commands.Context):
        self.bot = bot
        self._ctx = ctx
        self.exists = True
        self.current = None
        self.voice = None
        self.next = asyncio.Event()
        self.songs = SongQueue()

        self._loop = False
        self._volume = 0.5
        self.skip_votes = set()

        self.audio_player = bot.loop.create_task(self.audio_player_task())

    def __del__(self):
        self.audio_player.cancel()

    @property
    def loop(self):
        return self._loop

    @loop.setter
    def loop(self, value: bool):
        self._loop = value

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value: float):
        self._volume = value

    @property
    def is_playing(self):
        return self.voice and self.current

    async def audio_player_task(self):
        while True:
            self.next.clear()
            self.now = None

            if self.loop == False:
                try:
                    async with timeout(15):
                        self.current = await self.songs.get()
                except asyncio.TimeoutError:
                    self.bot.loop.create_task(self.stop())
                    self.exists = False
                    return
                
                self.current.source.volume = self._volume
                self.voice.play(self.current.source, after=self.play_next_song)
                await self.current.source.channel.send(embed=self.current.create_embed())
            elif self.loop == True:
                self.now = discord.FFmpegPCMAudio(self.current.source.stream_url, **YTDLSource.FFMPEG_OPTIONS)
                self.voice.play(self.now, after=self.play_next_song)
            
            await self.next.wait()

    def play_next_song(self, error=None):
        if error:
            raise VoiceError(str(error))

        self.next.set()

    def skip(self):
        self.skip_votes.clear()

        if self.is_playing:
            self.voice.stop()

    async def stop(self):
        self.songs.clear()

        if self.voice:
            await self.voice.disconnect()
            self.voice = None


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_states = {}

    def get_voice_state(self, ctx: commands.Context):
        state = self.voice_states.get(ctx.guild.id)
        if not state or not state.exists:
            state = VoiceState(self.bot, ctx)
            self.voice_states[ctx.guild.id] = state

        return state

    def cog_unload(self):
        for state in self.voice_states.values():
            self.bot.loop.create_task(state.stop())

    def cog_check(self, ctx: commands.Context):
        if not ctx.guild:
            raise commands.NoPrivateMessage('DM에서 사용할 수 없어요.')

        return True

    async def cog_before_invoke(self, ctx: commands.Context):
        ctx.voice_state = self.get_voice_state(ctx)

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        await ctx.send('문제가 생긴것 같아요: {} (유니버스 오류고쳐를 사용해보세요)'.format(str(error)))
        

    @commands.command(name='들어와', aliases=['join', 'j'], invoke_without_subcommand=True)
    async def _join(self, ctx: commands.Context):
        """제 우주의 힘으로 보이스채널에 들어갑니다."""

        destination = ctx.author.voice.channel
        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)
            return
        await ctx.send('포탈을 타고 보이스채널에 연결했어요.')
        ctx.voice_state.voice = await destination.connect()

    @commands.command(name='소환', aliases=['summon'])
    async def _summon(self, ctx: commands.Context, *, channel: discord.VoiceChannel = None):

        if not channel and not ctx.author.voice:
            raise VoiceError('어디에 가야할지 모르겠어요. 먼저 보이스채널에 들어가시면 따라갈게요.')

        destination = channel or ctx.author.voice.channel
        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)
            return

        ctx.voice_state.voice = await destination.connect()

    @commands.command(name='나가', aliases=['leave', 'l'])
    async def _leave(self, ctx: commands.Context):
        """포탈을 타고 보이스채널을 나갑니다."""

        if not ctx.voice_state.voice:
            return await ctx.send('저는 보이스채널에 없어요. (만약 오류라고 생각된다면 유니버스 오류고쳐를 사용해보세요.)')
        await ctx.send('포탈을 타고 보이스채널을 나갔습니다.')
        await ctx.voice_state.stop()
        del self.voice_states[ctx.guild.id]
        
    @commands.command(name='오류고쳐', aliases=['fix', 'fs', '오류고쳐봐'])
    async def _leavefs(self, ctx: commands.Context):
        try:
            voice_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
            await ctx.voice_state.songs.clear()
            await ctx.voice_state.stop()
            await voice_client.disconnect(force=True)
            del self.voice_states[ctx.guild.id]
            await ctx.send('포탈을 타고 보이스채널을 나갔습니다. (fs)')
        except:
            await ctx.send('오류를 찾을 수 없어요.')

    @commands.command(name='볼륨', aliases=['volume', 'vol'])
    async def _volume(self, ctx: commands.Context, *, volume: int):

        if not ctx.voice_state.is_playing:
            return await ctx.send('저는 음악을 틀고 있지 않아요.')

        if 0 > volume > 100:
            return await ctx.send('볼륨은 0과 100 사이여야해요.')
            
        ctx.voice_state.current.source.volume = volume / 100
        await ctx.send('현재 볼륨: {}%'.format(volume))
        
    @commands.command(name='일시중지', aliases=['pause', 'paus'])
    async def _pause(self, ctx: commands.Context):
        """"""

        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_playing():
            ctx.voice_state.voice.pause()
            await ctx.message.add_reaction('⏯')

    @commands.command(name='다시재생', aliases=['resume', 'res'])
    async def _resume(self, ctx: commands.Context):
        """"""

        if ctx.voice_state.voice.is_paused():
            ctx.voice_state.voice.resume()
            await ctx.message.add_reaction('⏯')

    @commands.command(name='멈춰', aliases=['stop'])
    async def _stop(self, ctx: commands.Context):
        """음악을 멈춥니다.
        """

        ctx.voice_state.songs.clear()
        
        if ctx.voice_state.is_playing:
            ctx.voice_state.voice.stop()
            await ctx.message.add_reaction('⏹')
        
            
    @commands.command(name='멈춰!')
    async def _stop1(self, ctx: commands.Context):
        """멈춰!
        """
        await ctx.send("멈춰!")
        ctx.voice_state.songs.clear()
        

        if ctx.voice_state.is_playing:
            ctx.voice_state.voice.stop()
            await ctx.message.add_reaction('⏹')

    @commands.command(name='스킵', aliases=['넘겨', 'skip', 's'])
    async def _skip(self, ctx: commands.Context):

        if not ctx.voice_state.is_playing:
            return await ctx.send('음악이 재생되고 있지 않아서 스킵할 수 없어요.')

        voter = ctx.message.author
        if voter == ctx.voice_state.current.requester:
            await ctx.message.add_reaction('⏭')
            ctx.voice_state.skip()

        elif voter.id not in ctx.voice_state.skip_votes:
            ctx.voice_state.skip_votes.add(voter.id)
            total_votes = len(ctx.voice_state.skip_votes)

            if total_votes >= 2:
                await ctx.message.add_reaction('⏭')
                ctx.voice_state.skip()
            else:
                await ctx.send('투표 **{}/2**'.format(total_votes))

        else:
            await ctx.send('당신은 이미 투표해 참여했습니다.')

    @commands.command(name='리스트', aliases=['queue', 'list'])
    async def _queue(self, ctx: commands.Context, *, page: int = 1):
        """음악 리스트를 보여줍니다.
        """

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('리스트에 음악이 없어요.')

        items_per_page = 10
        pages = math.ceil(len(ctx.voice_state.songs) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue = ''
        for i, song in enumerate(ctx.voice_state.songs[start:end], start=start):
            queue += '`{0}.` [**{1.source.title}**]({1.source.url})\n'.format(i + 1, song)

        embed = (discord.Embed(description='**{} 곡 리스트:**\n\n{}'.format(len(ctx.voice_state.songs), queue))
                 .set_footer(text='현재 페이지 {}/{}'.format(page, pages)))
        await ctx.send(embed=embed)

    @commands.command(name='섞어', aliases=['shuffle', 'sh'])
    async def _shuffle(self, ctx: commands.Context):
        """섞어드립니다."""

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('리스트에 음악이 없어요.')

        ctx.voice_state.songs.shuffle()
        await ctx.message.add_reaction('✅')

    @commands.command(name='제거', aliases=['remove', 'rem'])
    async def _remove(self, ctx: commands.Context, index: int):
        """곡 리스트에서 특정 곡을 제거 할 수 있습니다."""

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('리스트에 음악이 없어요.')

        ctx.voice_state.songs.remove(index - 1)
        await ctx.message.add_reaction('✅')

    @commands.command(name='반복재생', aliases=['loop'])
    async def _loop(self, ctx: commands.Context):

        if not ctx.voice_state.is_playing:
            return await ctx.send('지금 재생하고 있는 음악이 없어요.')

        ctx.voice_state.loop = not ctx.voice_state.loop
        await ctx.message.add_reaction('✅')
        if ctx.voice_state.loop == True:
            await ctx.send("**주의: 반복재생이 켜져있으므로 음악이 넘겨지지 않습니다! 음악을 넘기시려면 반복재생을 꺼주세요.**")
        else:
            await ctx.send("**반복재생이 꺼졌습니다.**")

    @commands.command(name='플레이', aliases=['틀어', '재생', 'play', 'p'])
    async def _play(self, ctx: commands.Context, *, search: str):
        guild = ctx.guild
        print("Requester ID: "+str(ctx.author.id))
        print("Requester name: "+str(ctx.author.name))
        print("Guild ID: "+str(guild.id))
        print("Guild Name: "+str(guild.name))
        print("Search Info: "+str(search))
        print("ctx: "+str(ctx))
        if not ctx.voice_state.voice:
            await ctx.invoke(self._join)

        if search.__contains__('?list='):
            async with ctx.typing():
                playlist, playlistTitle = self._playlist(search)
                for _title, _link in playlist.items():
                    try:
                        source = await YTDLSource.create_source(ctx, _link, loop=self.bot.loop)
                    except YTDLError as e:
                        await ctx.send('이 요청을 진행하는 도중에 문제가 발생하였습니다: {}'.format(str(e)))
                    else:
                        song = Song(source)
                        await ctx.voice_state.songs.put(song)
                await ctx.send(f'리스트에 `{playlist.__len__()}` 음악들 중 **{playlistTitle}를(을) 추가했어요.**')
        else:
            async with ctx.typing():
                try:
                    source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop)
                except YTDLError as e:
                    await ctx.send('이 요청을 진행하는 도중에 문제가 발생하였습니다: {}'.format(str(e)))
                else:
                    song = Song(source)

                    await ctx.voice_state.songs.put(song)
                    await ctx.send('리스트에 {}를(을) 추가했어요.'.format(str(source)))

    def _playlist(self, search: str):
        ydl_opts = {
          'ignoreerrors': True,
          'quit': True
        }

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            playlist_dict = ydl.extract_info(search, download=False)

            playlistTitle = playlist_dict['title']

            playlist = dict()
            for video in playlist_dict['entries']:
                print()

                if not video:
                    print('ERROR: 음악의 정보를 불러올 수 없습니다.')
                    continue
                
                for prop in ['id', 'title']:
                    print(prop, '--', video.get(prop))
                    playlist[video.get('title')] = 'https://www.youtube.com/watch?v=' + video.get('id')
            return playlist, playlistTitle
    @commands.command(name='검색', aliases=['search'])
    async def _search(self, ctx: commands.Context, *, search: str):
        """
        """
        async with ctx.typing():
            try:
                source = await YTDLSource.search_source(ctx, search, loop=self.bot.loop)
            except YTDLError as e:
                await ctx.send('오류가 발생하였습니다: {}'.format(str(e)))
            else:
                if source == 'sel_invalid':
                    await ctx.send('없는 목록이에요')
                elif source == 'cancel':
                    await ctx.send('취소되었습니다.')
                elif source == 'timeout':
                    await ctx.send(':alarm_clock: **시간 초과 ._.**')
                else:
                    if not ctx.voice_state.voice:
                        await ctx.invoke(self._join)

                    song = Song(source)
                    await ctx.voice_state.songs.put(song)
                    await ctx.send('리스트에 {}이라는 곡을 추가했어요.'.format(str(source)))
                    
    @commands.command(name='정보', aliases=['음악정보', 'np'])
    async def _now(self, ctx: commands.Context):

        await ctx.send(embed=ctx.voice_state.current.create_embed())
        
    @commands.command(name='업데이트내역', aliases=['패치노트', 'patchnotes'])
    async def _pn(self, ctx: commands.Context):
        f = open("./patch.yaml", 'r', encoding= 'UTF8')
        while 1:
            line = f.readline()
            if not line:
                break
            await ctx.send(line)
    #디자인 미완성


    @commands.Cog.listener("on_voice_state_update")
    async def voiceStateUpdate(self, member, before, after):
        voiceClient = discord.utils.get(self.bot.voice_clients, guild = member.guild) 
        
    @_join.before_invoke
    @_play.before_invoke
    async def ensure_voice_state(self, ctx: commands.Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandError('당신은 보이스채널에 연결되어있지 않는거 같아요.')

        if ctx.voice_client:
            if ctx.voice_client.channel != ctx.author.voice.channel:
                raise commands.CommandError('저는 이미 보이스채널에 있어요.')

bot = commands.AutoShardedBot(["유니버스 ","유니 ","!u","sa"], description=None)
#bot = commands.Bot(["유니버스 ","유니 ","!u","sa"], description='뮤직봇입니다.')
bot.add_cog(Music(bot))

@bot.remove_command('help')

@bot.command(name= '도와줘', aliases=['help', 'h'])
async def 도움말(ctx):
    owner_id = "380625576014381060"
    owner = await bot.fetch_user(owner_id)
    embed = discord.Embed(colour = discord.Colour.lighter_grey())
    embed.set_thumbnail(url="https://cdn.discordapp.com/avatars/709302768279486545/cd6c91c488fc25cc1fac9eae2aa97a61.png?size=128")
    embed.set_author(name = "명령어 표시")
    embed.add_field(name = "``유니버스 안녕``",value = "안녕하세요?",inline=True)
    embed.add_field(name = "``유니버스 들어와(join, j)``",value = "포탈을 타고 보이스채널에 들어옵니다.",inline=True)
    embed.add_field(name = "``유니버스 나가(leave, l)``",value = "포탈을 타고 보이스채널에서 나갑니다.",inline=True)
    embed.add_field(name = "``유니버스 오류고쳐(fix, fs)``",value = "오류를 해결하기 위한 명령어 입니다.",inline=True)
    embed.add_field(name = "``유니버스 플레이 (틀어 또는 재생 또는 play, p)``",value = "음악을 재생합니다.",inline=True)
    embed.add_field(name = "``유니버스 일시중지(pause, paus)``",value = "음악을 일시 중지합니다.",inline=True)
    embed.add_field(name = "``유니버스 다시재생(resume, res)``",value = "일시 중지되어있는 음악을 다시 재생합니다.",inline=True)
    embed.add_field(name = "``유니버스 멈춰(stop)``",value = "음악을 끕니다.",inline=True)
    embed.add_field(name = "``유니버스 스킵 (넘겨 또는 skip, s)``",value = "투표를 이용해서 음악을 넘깁니다.",inline=True)
    embed.add_field(name = "``유니버스 볼륨(volume, vol)``",value = "음악의 볼륨을 조절합니다.",inline=True)
    embed.add_field(name = "``유니버스 소환(summon)``",value = "저를 보이스채널로 소환합니다.",inline=True)
    embed.add_field(name = "``유니버스 반복재생(loop)``",value = "지금 재생하고 있는 음악을 다시 재생합니다. (한번 쓰면 반복, 다시 쓰면 반복중단)",inline=True)
    embed.add_field(name = "``유니버스 섞어(shuffle, sh)``",value = "음악 리스트를 섞어드립니다.",inline=True)
    embed.add_field(name = "``유니버스 리스트(queue, list)``",value = "음악 리스트를 보여줍니다.",inline=True)
    embed.add_field(name = "``유니버스 제거(remove, rem)``",value = "특정 곡을 리스트에서 제거할 수 있습니다",inline=True)
    embed.add_field(name = "``유니버스 검색(search) [검색할 곡(song to search)]``",value = "검색해서 곡을 고를수 있습니다.",inline=True)
    embed.add_field(name = "``유니버스 음악정보(np)``",value = "현재 재생하고 있는 음악 정보를 보여드립니다.",inline=True)
    embed.add_field(name = "``유니버스 패치노트(patchnotes)``",value = "업데이트 내역을 표시합니다.",inline=True)
    embed.add_field(name = "``접두사``",value = "봇의 접두사는 !u, 유니, 유니버스 (이)가 있습니다.",inline=True)
    embed.add_field(name = "``개발자``",value = owner.name+"#"+owner.discriminator,inline=True)
    await ctx.send(embed=embed)

@bot.event
async def on_ready():
    print('Logged in as:\n{0.user.name}\n{0.user.id}'.format(bot))
    print("유니버스는 준비되었습니다!")
    await bt(['우주를 여행하고 있어요. 도움말: "유니버스 도와줘"를 입력해주세요.'])


@bot.event
async def on_guild_join(guild):
    general = find(lambda x: x.name == '자유-채팅',  guild.text_channels)
    if general and general.permissions_for(guild.me).send_messages:
        embed = discord.Embed(colour = discord.Colour.lighter_grey())
        embed.add_field(name = "``안녕하세요?``",value = "안녕하세요. 저는 Music & Planet이라는 음악 봇이에요. 저를 초대해주셔서 감사해요.",inline=False)
        await general.send(embed=embed)
    else:
        welcome = await guild.create_text_channel("Music & Planet")
        embed = discord.Embed(colour = discord.Colour.lighter_grey())
        embed.add_field(name = "``안녕하세요?``",value = "안녕하세요. 저는 Music & Planet이라는 음악 봇이에요. 저를 초대해주셔서 감사해요.",inline=False)
        embed.add_field(name = "``참고``",value = "이 채널은 지워도 좋아요.",inline=False)
        await welcome.send(embed=embed)
        
#@bot.event
#async def on_voice_state_update(member, before, after):
#        voice_state = member.guild.voice_client
#        if voice_state is None:
#            # Exiting if the bot it's not connected to a voice channel
#            return
#
#        if len(voice_state.channel.members) == 1:
#            await ctx.send('보이스채널에 아무도 없으셔서 보이스채널을 나갔습니다.')
#            await ctx.voice_state.stop()
#            del self.voice_states[ctx.guild.id]        



#@bot.event
#async def on_guild_join(guild):
 #   for channel in guild.text_channels:
  #      if channel.permissions_for(guild.me).send_messages:
   #         embed = discord.Embed(colour = discord.Colour.lighter_grey())
    #        embed.add_field(name = "``안녕하세요?``",value = "안녕하세요. 저는 Music & Planet이라는 음악 봇이에요. 저를 초대해주셔서 감사해요.",inline=True)
     #       embed.add_field(name = "``._.``",value = "유니버스 공지채널추가 를 하시면 제가 공지를 드릴 수 있어요. 해주시면 좋겠어요.",inline=True)
      #      await channel.send(embed=embed)
       # break

#@bot.command()
#async def 공지(ctx, *, message : str):
#    print (str(message))
#    if ctx.author.id == 380625576014381060:
#        await ctx.send('관리자 권한 인증 성공')
#        try:
#            for chan in channels:
#                try:
#                    channel = bot.get_channel(chan)
#                    infoname=ctx.author.name
#                    info = discord.Embed(title='공지', description=(str(message)), color=discord.Colour.lighter_grey())
#                    info.set_thumbnail(url="https://cdn.discordapp.com/avatars/709302768279486545/cd6c91c488fc25cc1fac9eae2aa97a61.png?size=128")
#                    info.add_field(name="🔗", value="[Music & Planet 하트 눌러주기](https://is.gd/musicbot)", inline=False)
#                    info.set_footer(text=infoname+"이 작성함", icon_url=ctx.author.avatar_url)
#                    await channel.send(embed=info)
#                except Exception as e:
#                    await ctx.send(e)
#                    await ctx.send("오류: " + str(chan))
#        except Exception as e:
#                await ctx.send(e)

#@bot.command(pass_context=True)
#async def 공지채널추가(ctx):
#        if ctx.message.author.guild_permissions.administrator:
#                ad_ch = ctx.message.channel.id 
#
#                with open("channels.yaml", encoding='utf-8') as file:
#                        datachan = load(file)
#                if ad_ch in datachan["channels"]:
#                        await ctx.send('이미 등록되어있습니다.')
#                else:
#                        datachan["channels"].append(ad_ch)
#                        channels.append(ad_ch)
#
#                        with open('channels.yaml', 'w') as writer:
#                            yaml.dump(datachan, writer)

#                        await ctx.send('공지 채널이 추가되었습니다.')
#                return
#        if ctx.author.id == 380625576014381060:
#                ad_ch = ctx.message.channel.id 

#                with open("channels.yaml", encoding='utf-8') as file:
#                        datachan = load(file)
#                if ad_ch in datachan["channels"]:
#                        await ctx.send('이미 등록되어있습니다.')
#                else:
#                        datachan["channels"].append(ad_ch)
#                        channels.append(ad_ch)

#                        with open('channels.yaml', 'w') as writer:
#                            yaml.dump(datachan, writer)
#
#                        await ctx.send('공지 채널이 추가되었습니다.')
#                return
#        else:
#                await ctx.send('서버 관리자 권한이 필요합니다!')
                

#@bot.command(pass_context=True)
#async def 공지채널제거(ctx):
#        if ctx.message.author.guild_permissions.administrator:

#                re_ch = ctx.message.channel.id

#                with open("channels.yaml", encoding='utf-8') as file:
#                        datachan = load(file)
#                try:
#                        datachan["channels"].remove(re_ch)
#                        channels.remove(re_ch)

#                        with open('channels.yaml', 'w') as writer:
#                                yaml.dump(datachan, writer)

#                        await ctx.send('공지 채널목록에서 삭제되었습니다.')
#                except:
#                        await ctx.send('채널이 설정되어있지 않아 제거 불가능.')
#                return
#        if ctx.author.id == 380625576014381060:
#                re_ch = ctx.message.channel.id

#                with open("channels.yaml", encoding='utf-8') as file:
#                        datachan = load(file)
#                try:
#                        datachan["channels"].remove(re_ch)
#                        channels.remove(re_ch)

#                        with open('channels.yaml', 'w') as writer:
#                                yaml.dump(datachan, writer)

#                        await ctx.send('공지 채널목록에서 삭제되었습니다.')
#                except:
#                        await ctx.send('채널이 설정되어있지 않아 제거 불가능.')
#                return
#        else:
#                await ctx.send('서버 관리자 권한이 필요합니다!')
                

@bot.command()
async def 안녕(ctx):
    await ctx.send("안녕하세요?")

@bot.event
async def bt(games):
    await bot.wait_until_ready()

    while not bot.is_closed():
        for g in games:
            await bot.change_presence(status = discord.Status.online, activity=discord.Activity(type=discord.ActivityType.listening,name=g))
            await asyncio.sleep(8)
            
#dbkrpy.UpdateGuilds(bot,DBKR_token)


kbot_token = ""
client = discord.Client()
#kb = DiscordpyKoreanbots(client, kbot_token, run_task=True)
DBSBot = DBSkr.Client(
    bot=bot,
    koreanbots_token=kbot_token,
    topgg_token='None',
    uniquebots_token='None',
    autopost=True
)




bot.run("")                    