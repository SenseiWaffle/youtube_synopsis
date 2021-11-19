# synopsis.py

# Imports
from __future__ import unicode_literals
from youtubesearchpython.__future__ import VideosSearch
from pathlib import Path
from sklearn.cluster import KMeans
from collections import Counter
from progress.bar import IncrementalBar
import youtube_dl, asyncio, json, sys # Libs for video download
import argparse, cv2, os # Libs for frame captures
import numpy as np

cwd = os.getcwd() # Get current working directory
frame_dir = os.path.join( cwd, 'frames' )      # Directory for frame captures
synopses_dir = os.path.join( cwd, 'synopses' ) # Directory for finished synopses
tmpsqr = 'template_square.png'    # Path to square template
tmprec = 'template_rectangle.png' # Path to rectangle template
tmpsqr_height = 1080 # Height of square template in pixels
tmprec_height = 1920 # Height of rectangular template in pixels

# YoutubeDL formatting options
ydl_options = {
    'format' : '135',     # Quality - 137: 1080p, 136: 720p, 135: 480p, 134: 360p, 133: 240p
    'outtmpl' : '%(id)s.%(ext)s', # Output template: c\w\d\videoID.ext (ext should be .mp4)
    'noplaylist' : True   # If in doubt, download single video instead of playlist
}

"""
Search for one video with the input string and return the URL
"""
async def search( search_phrase ):
    videosSearch = VideosSearch( search_phrase, limit = 1 )
    videosResult = await videosSearch.next()

    return videosResult['result'][0][ 'link' ]

# Modified from https://stackoverflow.com/questions/33311153/python-extracting-and-saving-video-frames
# Answer from BeeBee8
"""
Take a screenshot for every interval of time specified
"""
async def extractImages( pathIn, pathOut, video_duration, num_slices ):
    # Calculate number of milliseconds between each frame for num_slice total frames
    time_skip = video_duration / num_slices

    count = 1
    vidcap = cv2.VideoCapture( pathIn )
    success,image = vidcap.read()
    success = True

    while success:
        vidcap.set( cv2.CAP_PROP_POS_MSEC,( count*time_skip ) )   # Skip n milliseconds until the next frame
        cv2.imwrite( os.path.join( pathOut, "frame%d.jpg" % count ), image) # Save frame as JPEG file
        success,image = vidcap.read()
        count += 1

# Taken from https://adamspannbauer.github.io/2018/03/02/app-icon-dominant-colors/
"""
Get the dominant (not the average) color from an image and return as a list
"""
async def get_dominant_color(image, k=5, image_processing_size = None):
    # Resize image if new dims provided
    if image_processing_size is not None:
        image = cv2.resize(image, image_processing_size,
                            interpolation = cv2.INTER_AREA)

    # Reshape the image to be a list of pixels
    image = image.reshape((image.shape[0] * image.shape[1], 3))

    # Cluster and assign labels to the pixels
    clt = KMeans(n_clusters = k)
    labels = clt.fit_predict(image)

    # Count labels to find most popular
    label_counts = Counter(labels)

    # Subset out most popular centroid
    dominant_color = clt.cluster_centers_[label_counts.most_common(1)[0][0]]

    # Returned list is in BGR format
    return list(dominant_color)

"""
Generate synopsis image
"""
async def create_synopsis( syn_img, color_seq, img_height, num_slices, video_title ):
    img = cv2.imread( syn_img )
    denominator = img_height / num_slices
    np.array(color_seq, int)

    for row in range( img_height ):
        img[ row, : ] = [ int(color_seq[int(row/denominator)][0]),
                          int(color_seq[int(row/denominator)][1]),
                          int(color_seq[int(row/denominator)][2]) ]

    cv2.imwrite( syn_img, img )

"""
main
"""
async def main( args ):
    search_term = args[0]
    num_slices = args[1]
    size = args[2]
    # Catch exception thrown if num_slices was not a number
    try:
        num_slices = int( num_slices )
    except:
        print( "\u26a0 Expected number in 2nd argument, using default value of 100. \u26a0" )
        num_slices = 100

    # Search for the video and grab the URL
    videoURL = await search( search_term )
    video_path = cwd
    video_duration = None
    video_ID = video_title = ''

    # Download the video with formatting and metadata, save file name and video duration
    with youtube_dl.YoutubeDL( ydl_options ) as ydl:
        metadata = ydl.extract_info( videoURL, download = False ) # Download metadata dict
        video_ID = metadata[ 'id' ]
        video_path = os.path.join( cwd, video_ID+'.mp4' )

        if os.path.exists( synopses_dir+'\\'+video_ID+'.png' ):
            print( "\u26a0 Synopsis already exists at '{}'. Recreating... \u26a0".format( synopses_dir+'\\'+video_ID+'.png' ) )

        video_duration = metadata[ 'duration' ] * 1000 # Convert seconds to milliseconds
        video_title = metadata[ 'title' ]

        ydl.download( [ videoURL ] ) # Download video

    # Ensure frame/synopses directories exists. If not, create the folders
    Path( frame_dir ).mkdir( parents = False, exist_ok = True )
    Path( synopses_dir ).mkdir( parents = False, exist_ok = True )

    # Grab frame captures
    await extractImages( video_path, frame_dir, video_duration, num_slices )

    color_seq = [] # List of dominant colors per frame
    frame_path_prefix = os.path.join( frame_dir, 'frame' ) # Path for frames

    # Get list of dominant colors for all frame captures in frame_dir
    with IncrementalBar( ' Generating Colors', max = num_slices ) as bar:
        for frame in range( 1, num_slices+1 ):
            frame_path = os.path.join( frame_path_prefix + str(frame) + '.jpg' )
            current_frame = cv2.imread( frame_path )
            cv2.cvtColor( current_frame, cv2.COLOR_BGR2HSV ) # get_dominant_color uses HSV format
            color_seq.append( await get_dominant_color( current_frame, 5, (64,48) ) )
            bar.next()
        bar.finish()

    synopsis = os.path.join( synopses_dir, video_ID+'.png' ) # Output dir\name

    # Adjust for templates
    tmpsize = ''
    tmpheight = 0
    if size.lower() == "square" or size.lower() == "sqr":
        tmpsize = tmpsqr
        tmpheight = tmpsqr_height
    else:
        tmpsize = tmprec
        tmpheight = tmprec_height

    # Generate synopsis
    os.system( "copy {} {}".format( tmpsize, synopsis ) ) # Make a copy of the template
    await create_synopsis( synopsis, color_seq, tmpheight, num_slices, video_title )

    # Clean up downloaded .mp4 and generated frames
    print( "Cleaning up resources..." )
    print( "\tRemoving {}...".format( video_ID+'.mp4' ) )
    os.remove( video_path ) # Delete downloaded video
    print( "\tRemoving frame captures..." )
    for file in os.listdir( frame_dir ):
        os.remove( os.path.join( frame_dir, file ) )
    print( "Finished clean up.")

    # Output synopsis name, number of frames used, and the search phrase used
    print( "Created {} ({} frames) from the search result '{}'\n".format( video_ID+'.png', num_slices, search_term ) )
    return os.path.join( synopses_dir, video_ID+'.png' )

"""
async to run main
"""
if __name__ == '__main__':
    #                  search_term, num_slices,  format
    args = sys.argv[1:] # Remove first item from passed arguements
    asyncio.run( main( args ) ) # 'sys.argv' is an array of cmd line args
