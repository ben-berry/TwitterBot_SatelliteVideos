# twitter bot
# upload daily satellite videos

import twitter
import os, sys, configparser, shutil, requests, subprocess
import time, schedule
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# Import parameters from credentials.cfg
class params:
    def __init__(self, cfile):
        config = configparser.ConfigParser()
        config.readfp(open(cfile))
        self.consumerKey = config.get('credentials','consumer_key')
        self.consumerSecret = config.get('credentials','consumer_secret')
        self.accessToken = config.get('credentials','access_token')
        self.accessSecret = config.get('credentials','access_secret')
        self.sector = config.get('parameters','sector')
        self.band = config.get('parameters','band')
        self.res = config.get('parameters','res')
        self.range = int(config.get('parameters','range'))
        self.sampling = int(config.get('parameters','sampling'))
        self.startDatetime = datetime.strptime(config.get('parameters','startDatetime'),'%Y-%m-%d-%H:%M')
        self.message = config.get('parameters','message')
        self.loop = config.get('parameters','loop')
        self.iflag = True
        self.mflag = True
        

####------------FUNCTION DEFINITIONS--------------####
# Help Documentation
def docs():
    doc = ("bot2.py \n\n"
           "Set all parameters in credentials.cfg \n"
           "Download images, generate video, and post to twitter\n\n"
           "To suppress any operations, use imput arguments:\n"
           "-t          no twitter output (will still test API keys)\n"
           "-i          do not download images\n"
           "-m          do not run ffmpeg")

# get twitter OAuth credentials from config.cfg
def twitter_api(p):
    api = twitter.Api(consumer_key = p.consumerKey,
                      consumer_secret = p.consumerSecret,
                      access_token_key = p.accessToken,
                      access_token_secret = p.accessSecret)
    return api

# Download images from GOES website for specified time range to 'images' directory
def get_images(p, url, img):
    # create or empty the images directory
    if not os.path.exists('images'):
        os.mkdir('images')
    else:
        for f in os.listdir('images'):
            os.unlink(os.path.join('images',f))
    os.chdir('images')

    ind = 0
    # Download all images within the time range
    for i in img:
        if ind%p.sampling == 0:
            try:
                print(img[ind])
                response = requests.get(url + img[ind], stream=True)
                with open('img-{:03}.jpg'.format(ind), 'wb') as out_file:
                    shutil.copyfileobj(response.raw, out_file)
                del response
            except requests.exceptions.RequestException as e:
                print(e) 
        else:
            pass
        ind = ind + 1

# Specify time range, download images, create video w/ ffmpeg
def create_media(p):		# p refers to the params class
    # GOES16 image index URL
    url = 'https://cdn.star.nesdis.noaa.gov/GOES16/ABI/' + p.sector + '/' + p.band + '/'

    # crawl url and fetch all available image urls
    source = requests.get(url).text
    soup = BeautifulSoup(source, 'lxml')

    startT = int(float(p.startDatetime.strftime('%Y%j%H%M')))
    endDatetime = p.startDatetime + timedelta(hours = p.range)
    endT = int(float(endDatetime.strftime('%Y%j%H%M')))
    img = []
    for a in soup('a', href=True):
        ref = a['href']
        fref = ref.replace('_','-')
        fref = fref.replace('.','-')
        frefs = fref.split('-')
        try:
            d = int(float(frefs[0]))
            r = frefs[-2]
            if (d > startT and
                d < endT and
                r == p.res):
                img.append(ref)
            else:
                pass
        except ValueError:
            pass
    print(img[0])
    if p.iflag:
        get_images(p, url, img)
        os.chdir('..')
    if p.mflag:
        # Create video file using ffmpeg
        cmd = ['ffmpeg', '-hide_banner', '-f', 'image2', '-framerate', '20', '-i', 'images/img-%03d.jpg', '-vcodec', 'libx264', '-preset', 'veryslow', '-crf', '25', '-g', '300', '-movflags', '+faststart', '-y', 'movie.mp4']
        subprocess.call(cmd)

    
        
# send tweet using twitter_api
def tweet_media(parms, med, flag):

    print(parms.message)
    api = twitter_api(parms)
    if flag:
        try:
            api.PostUpdate(parms.message, media=med)
        except:
            print('Twitter API error: ', sys.exc_info()[0])
    else:
        try:
            tst = api.VerifyCredentials()
            print(tst.screen_name)
        except:
            print('Twitter API error: ', sys.exc_info()[0])

def job(tweet):		# continuous mode - job to be scheduled
    parms = params('credentials.cfg')
    n = datetime.today() - timedelta(hours=24)
    parms.startDatetime = datetime(year=n.year, month=n.month, day=n.day, hour=10, minute=0)
    create_media(parms)
    vid = 'movie.mp4'
    parms.message = parms.startDatetime.strftime('24-hour GOES16 GEOCOLOR sequence for %A, %B %d, %Y.')
    tweet_media(parms, vid, tweet)

#####

def main():
    # read args and load credentials
    args = sys.argv
    parms = params('credentials.cfg')
    # if '-t' option, don't tweet
    if '-t' in args:
        tweet = False
    else:
        tweet = True
    # if '-h' option, display documentation
    if '-h' in args:
        docs() 

    # Single run mode
    # Testing: options '-i' do not download images
    #                  '-m' do not run ffmpeg
    # loop = 0  to run/post once
    elif any((c in 'im') for c in args[-1]) or parms.loop == 0:
        if '-i' in args:
            parms.iflag = False
        if '-m' in args:
            parms.mflag = False
        create_media(parms)
        vid = 'movie.mp4'
        tweet_media(parms, vid, tweet)
    # invalid args
    elif len(args) > 1:
        print('Option Error: use option \'-h\' for documentation')
    # Continuous Mode  -- uses "schedule"
    # Post previous day's video at 12:00 UTC every day
    # Video starts at 10:00 UTC as set in job() with length=parms.range
    else:
        schedule.every().day.at("12:00").do(job, tweet) 
        while True:
            schedule.run_pending()
            time.sleep(1)

        
main()        
    
