
import os
import glob
import re
import time
from collections import OrderedDict

import numpy as np
from scipy.io import wavfile
from scipy import interpolate
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
import proglog

import cv2
import decord
import pyqtgraph
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
from pyqtgraph.Qt.QtGui import QPixmap, QImage

from helpers import *

######################################################
# CONFIGURATION
# Note that some of the below could be loaded
#  from metadata files in the future.
######################################################

# Specify the root data directory, which contains subfolders for each device
data_dir_root = 'C:/Users/jdelp/Desktop/_whale_birthday_s3_data'

# Specify the layout of devices streams in the output video.
# Each value is (row, column, rowspan, colspan).
composite_layout = OrderedDict([
  ('Mavic (CETI)'         , (0, 0, 2, 2)),
  ('Mavic (DSWP)'         , (0, 2, 2, 2)),
  ('Canon (DelPreto)'     , (2, 1, 1, 1)),
  ('Canon (Gruber)'       , (2, 0, 1, 1)),
  ('Phone (DelPreto)'     , (2, 1, 1, 1)),
  ('GoPro (DelPreto)'     , (2, 1, 1, 1)),
  ('Phone (Aluma)'        , (2, 3, 1, 1)),
  ('Canon (DSWP)'         , (2, 2, 1, 1)),
  ('Phone (Baumgartner)'  , (3, 0, 1, 1)),
  ('Phone (Pagani)'       , (3, 1, 1, 1)),
  ('Phone (SalinoHugg)'   , (3, 2, 1, 1)),
  ('Hydrophone (Mevorach)', (4, 0, 1, 4)),
  ])

# Specify the time zone offset to get local time of this data collection day from UTC.
# Note that in the future this could probably be determined automatically.
localtime_offset_s = -4*3600
localtime_offset_str = '-0400'

# Specify offsets to add to timestamps extracted from filenames.
epoch_offsets_toAdd_s = {
  'CETI-DJI_MAVIC3-1'          : 0.67,
  'DSWP-DJI_MAVIC3-2'          : 2.17,
  'DG-CANON_EOS_1DX_MARK_III-1': 4*3600 + 204,
  'JD-CANON_REBEL_T5I'         : 14.28,
  'DSWP-CANON_EOS_70D-1'       : 4*3600,
  'DSWP-KASHMIR_MIXPRE6-1'     : 0,
  'Misc/Aluma'                 : 0,
  'Misc/Baumgartner'           : 0,
  'Misc/Pagani'                : 0,
  'Misc/SalinoHugg'            : 0,
  'Misc/DelPreto_Pixel5'       : 0,
  'Misc/DelPreto_GoPro'        : 0,
}

# Specify friendly names for each device that will be printed on the output video.
# This also specifies the device IDs that exist, and directories will be searched accordingly.
# For Misc devices, the keyword after "Misc/" will be used to find matching files in the Misc directory.
device_friendlyNames = {
  'CETI-DJI_MAVIC3-1'          : 'Mavic (CETI)',
  'DSWP-DJI_MAVIC3-2'          : 'Mavic (DSWP)',
  'DG-CANON_EOS_1DX_MARK_III-1': 'Canon (Gruber)',
  'JD-CANON_REBEL_T5I'         : 'Canon (DelPreto)',
  'DSWP-CANON_EOS_70D-1'       : 'Canon (DSWP)',
  'DSWP-KASHMIR_MIXPRE6-1'     : 'Hydrophone (Mevorach)',
  'Misc/Aluma'                 : 'Phone (Aluma)',
  'Misc/Baumgartner'           : 'Phone (Baumgartner)',
  'Misc/Pagani'                : 'Phone (Pagani)',
  'Misc/SalinoHugg'            : 'Phone (SalinoHugg)',
  'Misc/DelPreto_Pixel5'       : 'Phone (DelPreto)',
  'Misc/DelPreto_GoPro'        : 'GoPro (DelPreto)',
}

# Define the start/end time of the video.
# Some notable times are below for reference:
#   10:20:12 start of CETI Mavic
#   11:45:15 see baby in mom
#   11:45:48 see blood in water
#   11:53:30 whales nearing the boat
#   11:54:55 whales on other side of the boat
# output_video_start_time_str = '2023-07-08 11:48:45 -0400'
# output_video_start_time_str = '2023-07-08 11:53:53 -0400'
output_video_start_time_str = '2023-07-08 11:35:00 -0400'
output_video_duration_s = 50*60
output_video_fps = 10

# Define the output video size/resolution and compression.
composite_layout_column_width = 400 # also defines the scaling/resolution of photos/videos
subplot_border_size = 5 # ignored if the pyqtgraph subplot method is used
composite_layout_row_height = round(composite_layout_column_width/(1+7/9)) # Drone videos have an aspect ratio of 1.7777
output_video_compressed_rate_MB_s = 0.5 # None to not compress the video

# Define audio track added to the output video.
add_audio_track_to_output_video = True
output_audio_track_volume_gain_factor = 50 # 1 to not change volume
save_audio_track_as_separate_file = True

# Specify annotations on the output video.
output_video_banner_height_fraction = 0.04 # fraction of the final composite frame
output_video_banner_bg_color   = [100, 100, 100] # BGR
output_video_banner_text_color = [255, 255,   0] # BGR

# Configure audio plotting
audio_resample_rate_hz = 9600 # original rate is 96000
audio_plot_duration_beforeCurrentTime_s = 5
audio_plot_duration_afterCurrentTime_s  = 10
num_audio_channels_toPlot = 1
audio_plot_pens = [pyqtgraph.mkPen([255, 255, 255], width=4),
                   pyqtgraph.mkPen([255, 0, 255], width=1)]

# Configure how device timestamps are matched with output video frame timestamps.
timestamp_to_target_thresholds_s = { # each entry is the allowed time (before_current_frame, after_current_frame)
  'video': (1/output_video_fps*0.5, 1/output_video_fps*0.5),
  'audio': (1/output_video_fps*0.5, 1/output_video_fps*0.5),
  'image': (1, 1/output_video_fps), # first entry controls how long an image will be shown
}

# Method of creating the composite visualization frame.
use_pyqtgraph_subplots = False
use_opencv_subplots = True

# Visualization debugging options.
show_visualization_window = False
debug_composite_layout = False # Will show the layout with dummy data and then exit

# Derived configurations.
audio_plot_length_beforeCurrentTime = int(audio_resample_rate_hz * audio_plot_duration_beforeCurrentTime_s)
audio_plot_length_afterCurrentTime = int(audio_resample_rate_hz * audio_plot_duration_afterCurrentTime_s)
audio_plot_length = 1 + audio_plot_length_beforeCurrentTime + audio_plot_length_afterCurrentTime
audio_timestamps_toPlot_s = np.arange(start=0, stop=audio_plot_length)/audio_resample_rate_hz - audio_plot_duration_beforeCurrentTime_s

output_video_banner_fontScale = None # will be determined later based on the size of the banner
output_video_banner_textSize  = None # will be determined later once the font scale is computed

output_video_num_rows = max([layout_specs[0] + layout_specs[2] for layout_specs in composite_layout.values()])
output_video_num_cols = max([layout_specs[1] + layout_specs[3] for layout_specs in composite_layout.values()])
if use_opencv_subplots:
  output_video_width = composite_layout_column_width*output_video_num_cols + subplot_border_size*(output_video_num_cols+1)
  output_video_height = composite_layout_row_height*output_video_num_rows + subplot_border_size*(output_video_num_rows+1)
if use_pyqtgraph_subplots:
  output_video_width = composite_layout_column_width*output_video_num_cols
  output_video_height = composite_layout_row_height*output_video_num_rows
  
output_video_start_time_s = time_str_to_time_s(output_video_start_time_str)

output_video_filepath = os.path.join(data_dir_root,
                                     'composite_video_fps%d_duration%d_start%d_colWidth%d.mp4'
                                     % (output_video_fps, output_video_duration_s,
                                        1000*output_video_start_time_s,
                                        composite_layout_column_width))


######################################################
# HELPERS
######################################################

# Convert a device friendly name to a device ID.
def device_friendlyName_to_id(device_friendlyName_toFind):
  for (device_id, device_friendlyName) in device_friendlyNames.items():
    if device_friendlyName == device_friendlyName_toFind:
      return device_id

# Find a timestamp from a device that most closely matches a target timestamp.
# Will return the index of that matched timestamp within the device's array of timestamps.
# If there is no such timestamp within a specified threshold of the target, return None.
def get_index_for_time_s(timestamps_s, target_time_s, timestamp_to_target_thresholds_s):
  # Find the timestamp closest to the target.
  if timestamps_s.shape[0] == 1:
    # If there is only one timestamp, consider that the best one.
    best_index = 0
  else:
    # Find the index where the target timestamp would be inserted without changing the sort order.
    # This is much faster than using something like numpy.where(), since it can assume the input is sorted.
    next_index_pastTarget = timestamps_s.searchsorted(target_time_s)
    if next_index_pastTarget == timestamps_s.shape[0]:
      next_index_pastTarget -= 1
    # The above placed the target between two device timestamps.
    # Now see which one of those two is closer to the target.
    index_candidates = np.array([next_index_pastTarget-1, next_index_pastTarget])
    dt_candidates = abs(timestamps_s[index_candidates] - target_time_s)
    if dt_candidates[0] < dt_candidates[1]:
      best_index = index_candidates[0]
    else:
      best_index = index_candidates[1]
  # Check if the closest timestamp is within the threshold region of the target.
  if timestamps_s[best_index] < (target_time_s - timestamp_to_target_thresholds_s[0]):
    return None
  if timestamps_s[best_index] > (target_time_s + timestamp_to_target_thresholds_s[1]):
    return None
  # We found a good timestamp! Return its index.
  return best_index
  
# Add a banner to the output frame that displays the current timestamp.
def add_timestamp_banner(img, timestamp_s):
  global output_video_banner_height_fraction, output_video_banner_bg_color, output_video_banner_fontScale, output_video_banner_textSize
  
  # Add the bottom banner shading.
  output_video_banner_height = int(output_video_banner_height_fraction*img.shape[0])
  img = cv2.copyMakeBorder(img, 0, output_video_banner_height, 0, 0,
                           cv2.BORDER_CONSTANT, value=output_video_banner_bg_color)
  
  # Specify the text to write.
  timestamp_str = '%s (%0.3f)' % (time_s_to_str(timestamp_s, localtime_offset_s, localtime_offset_str),
                                  timestamp_s)
  
  # Compute the size of the text that will be drawn on the image.
  fontFace = cv2.FONT_HERSHEY_DUPLEX # cv2.FONT_HERSHEY_SIMPLEX
  fontThickness = 1 #2 if output_video_banner_height > 25 else 1
  if output_video_banner_fontScale is None:
    # If this is the first time, compute a font size to use.
    target_height = 0.5*output_video_banner_height
    target_width = 1e6 # don't filter on the width for now
    fontScale = 0
    textsize = None
    while (textsize is None) or ((textsize[1] < target_height) and (textsize[0] < target_width)):
      fontScale += 0.2
      textsize = cv2.getTextSize(timestamp_str, fontFace, fontScale, fontThickness)[0]
    fontScale -= 0.2
    textsize = cv2.getTextSize(timestamp_str, fontFace, fontScale, fontThickness)[0]
    output_video_banner_fontScale = fontScale
    output_video_banner_textSize = textsize
  else:
    # Otherwise, use the previously computed font size.
    output_video_banner_textSize = cv2.getTextSize(timestamp_str, fontFace, output_video_banner_fontScale, fontThickness)[0]
  
  # Compute a position that will center the text in the banner.
  text_position = [int(img.shape[1]/2 - output_video_banner_textSize[0]/2),
                   int(img.shape[0] - output_video_banner_height/2 + output_video_banner_textSize[1]/3)]
  
  # Draw the text on the image.
  img = cv2.putText(img, timestamp_str, text_position,
                    fontFace=fontFace, fontScale=output_video_banner_fontScale,
                    color=output_video_banner_text_color, thickness=fontThickness)
  return img


  
######################################################
# LOAD TIMESTAMPS AND DATA POINTERS
######################################################

# Will create a dictionary with following structure:
#   [device_id][filepath] = (timestamps_s, data)
#   If filepath points to a video:
#     timestamps_s is a numpy array of epoch timestamps for every frame
#     data is a cv2.VideoCapture object
#   If filepath points to a wav file:
#     timestamps_s is a numpy array of epoch timestamps for every sample
#     data is a num_samples x num_channels matrix of audio data
#   If filepath points to an image:
#     timestamps_s is a single-element numpy array with the epoch timestamps of the image
#     data is the filepath again
media_infos = {}

print()
print('Extracting timestamps and pointers to data for every frame/photo/audio')
for (device_id, device_friendlyName) in device_friendlyNames.items():
  media_infos[device_id] = {}
  # Find data files for this device.
  if 'Misc' in device_id:
    data_dir = os.path.join(data_dir_root, 'Misc')
    filename_keyword = device_id.split('/')[1]
    filepaths = glob.glob(os.path.join(data_dir, '*%s*' % filename_keyword))
  else:
    data_dir = os.path.join(data_dir_root, device_id)
    filepaths = glob.glob(os.path.join(data_dir, '*'))
  filepaths = [filepath for filepath in filepaths if not os.path.isdir(filepath)]
  print('  Found %4d files for device [%s]' % (len(filepaths), device_friendlyName))
  
  # Loop through each file to extract its timestamps and data pointers.
  for (file_index, filepath) in enumerate(filepaths):
    # Get the start time in epoch time
    filename = os.path.basename(filepath)
    start_time_ms = int(re.search('\d{13}', filename)[0])
    start_time_s = start_time_ms/1000.0
    start_time_s += epoch_offsets_toAdd_s[device_id]
    # Process the data/timestamps.
    if is_video(filepath):
      (row, col, rowspan, colspan) = composite_layout[device_friendlyName]
      (video_reader, frame_rate, num_frames) = get_video_reader(filepath,
                                                                target_width=colspan*composite_layout_column_width)
      frame_duration_s = 1/frame_rate
      timestamps_s = start_time_s + np.arange(start=0, stop=num_frames)*frame_duration_s
      media_infos[device_id][filepath] = (timestamps_s, video_reader)
    elif is_image(filepath):
      timestamps_s = np.array([start_time_s])
      media_infos[device_id][filepath] = (timestamps_s, filepath)
    elif is_audio(filepath):
      if file_index > 0:
        print('\r', end='')
      # if 'CETI23-280.1688831582000.WAV' not in filepath:
      #   print()
      #   continue
      print('    Loading and resampling file %2d/%2d     ' % (file_index+1, len(filepaths)), end='')
      (audio_rate, audio_data) = wavfile.read(filepath)
      # Resample the data.
      num_samples = audio_data.shape[0]
      timestamps_s = start_time_s + np.arange(start=0, stop=num_samples)/audio_rate
      fn_interpolate_audio = interpolate.interp1d(
          timestamps_s,  # x values
          audio_data,    # y values
          axis=0,        # axis of the data along which to interpolate
          kind='linear', # interpolation method, such as 'linear', 'zero', 'nearest', 'quadratic', 'cubic', etc.
          fill_value='extrapolate' # how to handle x values outside the original range
      )
      num_samples = int(num_samples * (audio_resample_rate_hz/audio_rate))
      timestamps_s_resampled = start_time_s + np.arange(start=0, stop=num_samples)/audio_resample_rate_hz
      audio_data_resampled = fn_interpolate_audio(timestamps_s_resampled)
      media_infos[device_id][filepath] = (timestamps_s_resampled, audio_data_resampled)
      if file_index == len(filepaths)-1:
        print()


######################################################
# INITIALIZE THE OUTPUT VIDEO
######################################################

# Generate timestamps for the output video frames.
output_video_num_frames = output_video_duration_s * output_video_fps
output_video_frame_duration_s = 1/output_video_fps
output_video_timestamps_s = output_video_start_time_s \
                            + np.arange(start=0,
                                        stop=output_video_num_frames)*output_video_frame_duration_s

if use_pyqtgraph_subplots:
  # # The below will make the background white if desired (the default is black).
  # pyqtgraph.setConfigOption('background', 'w')
  # pyqtgraph.setConfigOption('foreground', 'k')

  # Define a helper to update a subplot with new device data.
  # layout_widget is the item to update, such as an image view or an audio plot.
  # layout_specs is (row, col, rowspan, colspan) of the subplot location.
  # data is an image or audio data.
  # label is text to write on an image if desired.
  def update_subplot(layout_widget, layout_specs, data, label=None):
    if is_image(data):
      # Draw text on the image if desired.
      # Note that this is done after scaling, since scaling the text could make it unreadable.
      if label is not None:
        draw_text_on_image(data, label, pos=(0,-1),
                           font_scale=0.5, font_thickness=1, font=cv2.FONT_HERSHEY_DUPLEX)
      # Update the subplot with the image.
      pixmap = cv2_to_pixmap(data)
      layout_widget.setPixmap(pixmap)

    elif is_audio(data):
      # Update the line items with the new data.
      for channel_index in range(num_audio_channels_toPlot):
        layout_widget[channel_index].setData(audio_timestamps_toPlot_s, data[:,channel_index])
      # Plot a vertical current time marker, and update the y range.
      if np.amax(data) < 50:
        layout_widget[-1].setData([0, 0], np.amax(data)*np.array([-50, 50]))
        audio_plotWidget.setYRange(-50, 50) # avoid zooming into an empty plot
      else:
        layout_widget[-1].setData([0, 0], np.amax(data)*np.array([-1, 1]))
        audio_plotWidget.enableAutoRange(enable=0.9) # allow automatic scaling that shows 90% of the data

  # Create the plotting layout.

  # Store the widgets/plots, and dummy data for each one so it can be cleared when no device data is available.
  # Will use layout_specs as the key, in case multiple devices are in the same subplot.
  layout_widgets = {}
  dummy_datas = {}
  # Initialize the layout.
  # The top level will be a GraphicsLayout, since that seems easier to export to an image.
  # Then the main level will be a GridLayout to flexibly arrange the visualized data streams.
  app = QtWidgets.QApplication([])
  graphics_layout = pyqtgraph.GraphicsLayoutWidget()
  grid_layout = QtWidgets.QGridLayout()
  graphics_layout.setLayout(grid_layout)
  # Initialize the visualizations for each stream.
  for (device_friendlyName, layout_specs) in composite_layout.items():
    device_id = device_friendlyName_to_id(device_friendlyName)
    (row, col, rowspan, colspan) = layout_specs
    # If a widget has already been created for this subplot location, just use that one for this device too.
    if str(layout_specs) in layout_widgets:
      continue
    # Load information about the stream.
    media_file_infos = media_infos[device_id]
    example_filepath = list(media_file_infos.keys())[0]
    (example_timestamps_s, example_data) = media_file_infos[example_filepath]
    # Create a layout based on the data type.
    if is_video(example_filepath) or is_image(example_filepath):
      if is_video(example_filepath):
        success, example_image = load_frame(example_data, 0,
                                            target_width=composite_layout_column_width*colspan,
                                            target_height=composite_layout_row_height*rowspan)
      elif is_image(example_filepath):
        example_image = load_image(example_filepath,
                                   target_width=composite_layout_column_width*colspan,
                                   target_height=composite_layout_row_height*rowspan)
      else:
        raise AssertionError('Thought it was a video or image, but apparently not')
      # Create a gray image the size of the real image that can be used to see the composite layout.
      blank_image = 100*np.ones_like(example_image)
      # Create a widget to show the image, that is set to the target height.
      image_labelWidget = QtWidgets.QLabel()
      grid_layout.addWidget(image_labelWidget, *layout_specs,
                            alignment=pyqtgraph.QtCore.Qt.AlignmentFlag.AlignCenter)
      grid_layout.setRowMinimumHeight(layout_specs[0], composite_layout_row_height)
      update_subplot(image_labelWidget, layout_specs, blank_image)
      # Store the widget and a black image as dummy data.
      layout_widgets[str(layout_specs)] = image_labelWidget
      dummy_datas[str(layout_specs)] = 0*blank_image
    elif is_audio(example_filepath):
      # Create a plot for the audio data, that is set to the target height.
      audio_plotWidget = pyqtgraph.PlotWidget()
      grid_layout.addWidget(audio_plotWidget, *layout_specs, alignment=pyqtgraph.QtCore.Qt.AlignmentFlag.AlignCenter)
      grid_layout.setRowMinimumHeight(layout_specs[0], composite_layout_row_height)
      # Generate random noise that can be used to preview the visualization layout.
      random_audio = 500*np.random.normal(size=(audio_plot_length, num_audio_channels_toPlot))
      # Ensure the widget fills the width of the entire allocated region of subplots.
      audio_plotWidget.setMinimumWidth(composite_layout_column_width*layout_specs[3])
      # Plot the dummy data, and store handles to the lines so their lines can be updated later.
      # Currently assumes 2 channels of audio data.
      h_lines = []
      for channel_index in range(num_audio_channels_toPlot):
        h_lines.append(audio_plotWidget.plot(audio_timestamps_toPlot_s, random_audio[:,channel_index],
                                             pen=audio_plot_pens[channel_index]))
      h_lines.append(audio_plotWidget.plot([0, 0], [-500, 500], pen=pyqtgraph.mkPen([0, 150, 150], width=7)))
      # Store the line handles and dummy data.
      layout_widgets[str(layout_specs)] = h_lines
      dummy_datas[str(layout_specs)] = 0*random_audio

  # Draw the visualization with dummy data.
  QtCore.QCoreApplication.processEvents()
  graphics_layout.setWindowTitle('Happy Birthday!')
  if show_visualization_window or debug_composite_layout:
    graphics_layout.show()
    if debug_composite_layout:
      app.exec()
      import sys
      sys.exit()

######################################################
# Alternative option using OpenCV instead of PyQtGraph for the subplotting/layout

if use_opencv_subplots:
  def get_slice_indexes_for_subplot_update(layout_specs, subplot_img):
    (row, col, rowspan, colspan) = layout_specs
    # Get the indexes of the total space allocated to this subplot.
    start_col_index = subplot_border_size*(col+1) + composite_layout_column_width*(col)
    end_col_index = start_col_index + composite_layout_column_width*(colspan) + subplot_border_size*(colspan-1) - 1
    start_row_index = subplot_border_size*(row+1) + composite_layout_row_height*(row)
    end_row_index = start_row_index + composite_layout_row_height*(rowspan) + subplot_border_size*(rowspan-1) - 1
    # Center the desired image in the subplot.
    subplot_width = end_col_index - start_col_index + 1
    pad_left = (subplot_width - subplot_img.shape[1])//2
    pad_right = (subplot_width - subplot_img.shape[1]) - pad_left
    start_col_index += pad_left
    end_col_index -= pad_right
    subplot_height = end_row_index - start_row_index + 1
    pad_top = (subplot_height - subplot_img.shape[0])//2
    pad_bottom = (subplot_height - subplot_img.shape[0]) - pad_top
    start_row_index += pad_top
    end_row_index -= pad_bottom
    # Return the slice indexes.
    # Increment end indexes since the end indexes computed above were considered inclusive,
    #  but slicing will be exclusive of the end indexes.
    return (start_row_index, end_row_index+1, start_col_index, end_col_index+1)
    
  # Define a helper to update a subplot with new device data.
  # composite_img is the composite frame image to update.
  # layout_specs is (row, col, rowspan, colspan) of the subplot location.
  # data is an image or audio data.
  # image_label is text to write on an image if desired.
  # audio_graphics_layout and audio_plot_handles are the audio plot items if updating audio.
  def update_subplot(composite_img, layout_specs, data,
                     image_label=None,
                     audio_graphics_layout=None, audio_plot_handles=None):
    if is_image(data):
      # Draw text on the image if desired.
      # Note that this is done after scaling, since scaling the text could make it unreadable.
      if image_label is not None:
        draw_text_on_image(data, image_label, pos=(0,-1),
                           font_scale=0.7, font_thickness=1, font=cv2.FONT_HERSHEY_DUPLEX)
      # Update the subplot within the image.
      subplot_indexes = get_slice_indexes_for_subplot_update(layout_specs, data)
      composite_img[subplot_indexes[0]:subplot_indexes[1], subplot_indexes[2]:subplot_indexes[3]] = data
    
    elif is_audio(data):
      # Update the line items with the new data.
      for channel_index in range(num_audio_channels_toPlot):
        audio_plot_handles[channel_index].setData(audio_timestamps_toPlot_s, data[:,channel_index])
      # Plot a vertical current time marker, and update the y range.
      if np.amax(data) < 50:
        audio_plot_handles[-1].setData([0, 0], np.amax(data)*np.array([-50, 50]))
        audio_plotWidget.setYRange(-50, 50) # avoid zooming into an empty plot
      else:
        audio_plot_handles[-1].setData([0, 0], np.amax(data)*np.array([-1, 1]))
        audio_plotWidget.enableAutoRange(enable=0.9) # allow automatic scaling that shows 90% of the data
      # Grab the plot as an image.
      img = audio_graphics_layout.grab().toImage()
      img = qimage_to_numpy(img)
      img = np.array(img[:,:,0:3])
      (_, _, rowspan, colspan) = layout_specs
      img = scale_image(img, target_width=composite_layout_column_width*colspan,
                             target_height=composite_layout_row_height*rowspan)
      # Update the subplot with the image.
      composite_img = update_subplot(composite_img, layout_specs, img, image_label=image_label)
    
    return composite_img
  
  # Create the blank image to use as the background.
  composite_img_blank = np.zeros(shape=(output_video_height, output_video_width, 3), dtype=np.uint8)
  composite_img_dummy = composite_img_blank.copy()

  # Store dummy data for each subplot so it can be cleared when no device data is available.
  # Also store the widgets/plots for each audio visualization so they can be updated later.
  # Will use layout_specs as the key, in case multiple devices are in the same subplot.
  audio_graphics_layouts = {}
  audio_grid_layouts = {}
  audio_plot_handles = {}
  dummy_datas = {}
  # Initialize pyqtgraph.
  app = QtWidgets.QApplication([])
  # Initialize the visualizations for each stream.
  for (device_friendlyName, layout_specs) in composite_layout.items():
    device_id = device_friendlyName_to_id(device_friendlyName)
    (row, col, rowspan, colspan) = layout_specs
    # If a widget has already been created for this subplot location, just use that one for this device too.
    if str(layout_specs) in dummy_datas:
      continue
    # Load information about the stream.
    media_file_infos = media_infos[device_id]
    example_filepath = list(media_file_infos.keys())[0]
    (example_timestamps_s, example_data) = media_file_infos[example_filepath]
    # Create a layout and dummy data based on the stream type.
    if is_video(example_filepath) or is_image(example_filepath):
      if is_video(example_filepath):
        success, example_image = load_frame(example_data, 0,
                                            target_width=composite_layout_column_width*colspan,
                                            target_height=composite_layout_row_height*rowspan)
      elif is_image(example_filepath):
        example_image = load_image(example_filepath,
                                   target_width=composite_layout_column_width*colspan,
                                   target_height=composite_layout_row_height*rowspan)
      else:
        raise AssertionError('Thought it was a video or image, but apparently not')
      # Create a gray image the size of the real image that can be used to see the composite layout.
      blank_image = 100*np.ones_like(example_image)
      # Update the dummy composite image with the dummy image.
      update_subplot(composite_img_dummy, layout_specs, example_image,
                     image_label=device_friendlyName)
      # Store a black image as dummy data.
      dummy_datas[str(layout_specs)] = 0*blank_image
    elif is_audio(example_filepath):
      # Initialize the layout.
      # The top level will be a GraphicsLayout, since that seems easier to export to an image.
      # Then the main level will be a GridLayout to flexibly arrange the visualized data streams.
      graphics_layout = pyqtgraph.GraphicsLayoutWidget()
      grid_layout = QtWidgets.QGridLayout()
      graphics_layout.setLayout(grid_layout)
      # Create a plot for the audio data, that is set to the target size.
      audio_plotWidget = pyqtgraph.PlotWidget()
      grid_layout.addWidget(audio_plotWidget, *layout_specs, alignment=pyqtgraph.QtCore.Qt.AlignmentFlag.AlignCenter)
      graphics_layout.setGeometry(10, 10, composite_layout_column_width*layout_specs[3],
                                          composite_layout_row_height*layout_specs[2])
      # Ensure the widget fills the width of the entire allocated region of subplots.
      grid_layout.setRowMinimumHeight(layout_specs[0], composite_layout_row_height)
      audio_plotWidget.setMinimumWidth(composite_layout_column_width*layout_specs[3])
      # Generate random noise that can be used to preview the visualization layout.
      random_audio = 500*np.random.normal(size=(audio_plot_length, num_audio_channels_toPlot))
      # Plot the dummy data, and store handles to the lines so their lines can be updated later.
      # Currently assumes 2 channels of audio data.
      h_lines = []
      for channel_index in range(num_audio_channels_toPlot):
        h_lines.append(audio_plotWidget.plot(audio_timestamps_toPlot_s, random_audio[:,channel_index],
                                             pen=audio_plot_pens[channel_index]))
      h_lines.append(audio_plotWidget.plot([0, 0], [-500, 500], pen=pyqtgraph.mkPen([0, 150, 150], width=7)))
      # Update the example composite image.
      update_subplot(composite_img_dummy, layout_specs, random_audio,
                     image_label=None,
                     audio_graphics_layout=graphics_layout, audio_plot_handles=h_lines)
      # Store the line handles and dummy data.
      audio_graphics_layouts[str(layout_specs)] = graphics_layout
      audio_grid_layouts[str(layout_specs)] = grid_layout
      audio_plot_handles[str(layout_specs)] = h_lines
      dummy_datas[str(layout_specs)] = 0*random_audio
  
      # Show the window if desired.
      QtCore.QCoreApplication.processEvents()
      if show_visualization_window:
        graphics_layout.show()

  # Show the window if desired.
  if show_visualization_window or debug_composite_layout:
    cv2.imshow('Happy Birthday!', composite_img_dummy)
    cv2.waitKey(1)
    if debug_composite_layout:
      cv2.waitKey(0)
      import sys
      sys.exit()
    

######################################################
# CREATE A VIDEO
######################################################

print()
print('Generating an output video with %d frames' % output_video_timestamps_s.shape[0])

# Will store some timing information for finding processing bottlenecks.
duration_s_updatePlots_total = 0
duration_s_updatePlots_audio = 0
duration_s_getIndex = 0
duration_s_readImages = 0
readImages_count = 0
readVideos_count = 0
duration_s_readVideos = 0
duration_s_audioParsing = 0
duration_s_exportFrame = 0
duration_s_writeFrame = 0

# Generate a frame for every desired timestamp.
composite_video_writer = None
if use_opencv_subplots:
  composite_img_current = composite_img_blank.copy()
last_status_time_s = 0
layouts_updated = {}
layouts_showing_dummyData = dict([(str(layout_specs), False) for layout_specs in composite_layout.values()])
layouts_prevState = dict([(str(layout_specs), None) for layout_specs in composite_layout.values()])
start_loop_time_s = time.time()
for (frame_index, current_time_s) in enumerate(output_video_timestamps_s):
  # Print periodic status updates.
  if time.time() - last_status_time_s > 10:
    print(' Processing frame %6d/%6d (%0.2f%%) for time %10d (%s)' %
          (frame_index+1, output_video_num_frames, 100*(frame_index+1)/output_video_num_frames,
           current_time_s, time_s_to_str(current_time_s, localtime_offset_s, localtime_offset_str)))
    last_status_time_s = time.time()
  
  # Mark that no subplot layouts have been updated.
  for (device_friendlyName, layout_specs) in composite_layout.items():
    layouts_updated[str(layout_specs)] = False

  # Loop through each specified device stream.
  # Note that multiple devices may be mapped to the same layout position;
  #  in that case the last device with data for this timestep will be used.
  for (device_friendlyName, layout_specs) in composite_layout.items():
    device_id = device_friendlyName_to_id(device_friendlyName)
    (row, col, rowspan, colspan) = layout_specs
    media_file_infos = media_infos[device_id]
    # For each media file associated with this device, see if it has data for this timestep.
    # Note that the device may have multiple images that match this timestamp, but only the first will be used.
    for (filepath, (timestamps_s, data)) in media_file_infos.items():
      # Handle videos.
      if is_video(filepath):
        # Find the data index closest to the current time (if any).
        t0 = time.time()
        data_index = get_index_for_time_s(timestamps_s, current_time_s, timestamp_to_target_thresholds_s['video'])
        duration_s_getIndex += time.time() - t0
        if data_index is not None:
          # Only spend time loading data and updating the plot if it changed since last frame.
          if (filepath, data_index) == layouts_prevState[str(layout_specs)]:
            layouts_updated[str(layout_specs)] = True
            layouts_showing_dummyData[str(layout_specs)] = False
            break # don't check any more media for this device
          # Read the video frame at the desired index.
          t0 = time.time()
          success, img = load_frame(data, data_index,
                                    target_width=composite_layout_column_width*colspan,
                                    target_height=composite_layout_row_height*rowspan)
          
          if success:
            duration_s_readVideos += time.time() - t0
            readVideos_count += 1
            # Update the subplot with the video frame.
            t0 = time.time()
            if use_pyqtgraph_subplots:
              update_subplot(layout_widgets[str(layout_specs)], layout_specs, img, label=device_friendlyName)
            elif use_opencv_subplots:
              img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
              update_subplot(composite_img_current, layout_specs, img, image_label=device_friendlyName)
            layouts_updated[str(layout_specs)] = True
            layouts_showing_dummyData[str(layout_specs)] = False
            layouts_prevState[str(layout_specs)] = (filepath, data_index)
            duration_s_updatePlots_total += time.time() - t0
            break # don't check any more media for this device
      # Handle photos.
      elif is_image(filepath):
        # Find the data index closest to the current time (if any).
        t0 = time.time()
        data_index = get_index_for_time_s(timestamps_s, current_time_s, timestamp_to_target_thresholds_s['image'])
        duration_s_getIndex += time.time() - t0
        if data_index is not None:
          # Only spend time loading data and updating the plot if it changed since last frame.
          if (filepath, data_index) == layouts_prevState[str(layout_specs)]:
            layouts_updated[str(layout_specs)] = True
            layouts_showing_dummyData[str(layout_specs)] = False
            break # don't check any more media for this device
          # Read the desired photo.
          t0 = time.time()
          img = load_image(filepath,
                           target_width=composite_layout_column_width*colspan,
                           target_height=composite_layout_row_height*rowspan)
          duration_s_readImages += time.time() - t0
          readImages_count += 1
          # Update the subplot with the photo.
          t0 = time.time()
          if use_pyqtgraph_subplots:
            update_subplot(layout_widgets[str(layout_specs)], layout_specs, img, label=device_friendlyName)
          elif use_opencv_subplots:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            update_subplot(composite_img_current, layout_specs, img, image_label=device_friendlyName)
          layouts_updated[str(layout_specs)] = True
          layouts_showing_dummyData[str(layout_specs)] = False
          layouts_prevState[str(layout_specs)] = (filepath, data_index)
          duration_s_updatePlots_total += time.time() - t0
          break # don't check any more media for this device
      # Handle audio.
      elif is_audio(filepath):
        # Find the data index closest to the current time (if any).
        t0 = time.time()
        data_index = get_index_for_time_s(timestamps_s, current_time_s, timestamp_to_target_thresholds_s['audio'])
        duration_s_getIndex += time.time() - t0
        if data_index is not None:
          # Only spend time loading data and updating the plot if it changed since last frame.
          if (filepath, data_index) == layouts_prevState[str(layout_specs)]:
            layouts_updated[str(layout_specs)] = True
            layouts_showing_dummyData[str(layout_specs)] = False
            break # don't check any more media for this device
          t0 = time.time()
          # Get the audio rate and number of channels.
          audio_sps = round((timestamps_s.shape[0]-1)/(timestamps_s[-1] - timestamps_s[0])) # NOTE: using first/last indexes is much faster than using max/min
          audio_num_channels = data.shape[1]
          # Get the start/end indexes of the data to plot.
          # Note that these may be negative or beyond the bounds of the data, indicating padding is needed.
          start_index = data_index - audio_plot_length_beforeCurrentTime
          end_index = data_index + audio_plot_length_afterCurrentTime + 1
          # Determine how much silence should be added to the data to fill the plot.
          num_toPad_pre = 0 if start_index >= 0 else -start_index
          num_toPad_post = 0 if end_index <= data.shape[0] else end_index - data.shape[0]
          # Adjust the start/end indexes to be within the data bounds.
          start_index = max(0, start_index)
          end_index = min(data.shape[0], end_index)
          # Get the data and pad it as needed.
          data_toPlot = data[start_index:end_index]
          data_toPlot = np.vstack([np.zeros((num_toPad_pre, audio_num_channels)),
                                   data_toPlot,
                                   np.zeros((num_toPad_post, audio_num_channels))])
          duration_s_audioParsing += time.time() - t0
          # Update the subplot with the waveform segment.
          t0 = time.time()
          if use_pyqtgraph_subplots:
            update_subplot(layout_widgets[str(layout_specs)], layout_specs, data_toPlot)
          elif use_opencv_subplots:
            update_subplot(composite_img_current, layout_specs, data_toPlot,
                           image_label=None,
                           audio_graphics_layout=audio_graphics_layouts[str(layout_specs)],
                           audio_plot_handles=audio_plot_handles[str(layout_specs)])
          layouts_updated[str(layout_specs)] = True
          layouts_showing_dummyData[str(layout_specs)] = False
          layouts_prevState[str(layout_specs)] = (filepath, data_index)
          duration_s_updatePlots_total += time.time() - t0
          duration_s_updatePlots_audio += time.time() - t0
          break # don't check any more media for this device

  # If a layout was not updated, show its dummy data.
  # But only spend time updating it if it isn't already showing dummy data.
  for (device_friendlyName, layout_specs) in composite_layout.items():
    if not layouts_updated[str(layout_specs)] and not layouts_showing_dummyData[str(layout_specs)]:
      device_id = device_friendlyName_to_id(device_friendlyName)
      t0 = time.time()
      if use_pyqtgraph_subplots:
        update_subplot(layout_widgets[str(layout_specs)], layout_specs, dummy_datas[str(layout_specs)])
      elif use_opencv_subplots:
        if str(layout_specs) in audio_graphics_layouts:
          update_subplot(composite_img_current, layout_specs, dummy_datas[str(layout_specs)],
                         image_label=None,
                         audio_graphics_layout=audio_graphics_layouts[str(layout_specs)],
                         audio_plot_handles=audio_plot_handles[str(layout_specs)])
          duration_s_updatePlots_audio += time.time() - t0
        else:
          update_subplot(composite_img_current, layout_specs, dummy_datas[str(layout_specs)],
                         image_label=None)
      layouts_showing_dummyData[str(layout_specs)] = True
      duration_s_updatePlots_total += time.time() - t0
      layouts_prevState[str(layout_specs)] = None

  # Refresh the figure with the updated subplots.
  if use_pyqtgraph_subplots:
    t0 = time.time()
    QtCore.QCoreApplication.processEvents()
    duration_s_updatePlots_total += time.time() - t0

  # Render the figure into a composite frame image.
  if use_pyqtgraph_subplots:
    t0 = time.time()
    exported_img = graphics_layout.grab().toImage()
    exported_img = qimage_to_numpy(exported_img)
    exported_img = np.array(exported_img[:,:,0:3])
    exported_img = scale_image(exported_img, target_width=output_video_width, target_height=output_video_height)
    duration_s_exportFrame += time.time() - t0
  elif use_opencv_subplots:
    exported_img = composite_img_current
  # Add a banner with the current timestamp.
  exported_img = add_timestamp_banner(exported_img, current_time_s)
  # Write the frame to the output video.
  if output_video_filepath is not None:
    t0 = time.time()
    # Create the video writer if this is the first frame, since we now know the frame dimensions.
    if composite_video_writer is None:
      composite_video_writer = cv2.VideoWriter(output_video_filepath,
                                               cv2.VideoWriter_fourcc(*'MJPG') if '.avi' in output_video_filepath.lower() else cv2.VideoWriter_fourcc(*'MP4V'),
                                               output_video_fps, [exported_img.shape[1], exported_img.shape[0]])
    composite_video_writer.write(exported_img)
    duration_s_writeFrame += time.time() - t0

# All done!
total_duration_s = time.time() - start_loop_time_s
print()
print('Generated composite video in %d seconds' % total_duration_s)
print()

# Release the output video.
if composite_video_writer is not None:
  composite_video_writer.release()

# Release video readers.
for (device_id, media_file_infos) in media_infos.items():
  for (filepath, (timestamps_s, data)) in media_file_infos.items():
    if isinstance(data, cv2.VideoCapture):
      data.release()

# Print timing information.
print()
print('Configuration:')
print('  Audio rate     : %d Hz' % audio_resample_rate_hz)
print('  Audio plot duration: [-%d %d] seconds' % (audio_plot_duration_beforeCurrentTime_s, audio_plot_duration_afterCurrentTime_s))
print('  Column width   : %d' % composite_layout_column_width)
print('  Output duration: %d' % output_video_duration_s)
print('  Output rate    : %d' % output_video_fps)
print('  Show visualization window: %s' % show_visualization_window)
print('Processing duration: ')
print('  Total duration: %0.3f seconds' % total_duration_s)
print('  Frame count   : %d' % output_video_timestamps_s.shape[0])
print('  Frame rate    : %0.1f frames per second' % (output_video_timestamps_s.shape[0]/total_duration_s))
print('  Speed factor  : %0.2f x real time' % (output_video_duration_s/total_duration_s))
print('Processing breakdown: ')
print('  UpdatePlots (total) : %6.2f%% (%0.3f seconds)' % (100 * duration_s_updatePlots_total / total_duration_s, duration_s_updatePlots_total))
print('  UpdatePlots (audio) : %6.2f%% (%0.3f seconds)' % (100 * duration_s_updatePlots_audio / total_duration_s, duration_s_updatePlots_audio))
print('  GetIndex            : %6.2f%% (%0.3f seconds)' % (100*duration_s_getIndex/total_duration_s, duration_s_getIndex))
print('  ReadImages          : %6.2f%% (%0.3f seconds) (%d calls)' % (100*duration_s_readImages/total_duration_s, duration_s_readImages, readImages_count))
print('  ReadVideos          : %6.2f%% (%0.3f seconds) (%d calls)' % (100*duration_s_readVideos/total_duration_s, duration_s_readVideos, readVideos_count))
print('  ParseAudio          : %6.2f%% (%0.3f seconds)' % (100*duration_s_audioParsing/total_duration_s, duration_s_audioParsing))
print('  ExportFrame         : %6.2f%% (%0.3f seconds)' % (100*duration_s_exportFrame/total_duration_s, duration_s_exportFrame))
print('  WriteFrame          : %6.2f%% (%0.3f seconds)' % (100*duration_s_writeFrame/total_duration_s, duration_s_writeFrame))
print()

######################################################
# COMPRESS THE VIDEO
######################################################

if output_video_compressed_rate_MB_s is not None:
  print('Compressing the output video to %g MB/s (total target size: %0.2f MB)'
        % (output_video_compressed_rate_MB_s, output_video_compressed_rate_MB_s*output_video_duration_s))
  t0 = time.time()
  output_video_compressed_filepath = '%s_compressed%sMBs%s' \
                                      % (os.path.splitext(output_video_filepath)[0],
                                         ('%0.2f' % output_video_compressed_rate_MB_s).replace('.','-'),
                                         os.path.splitext(output_video_filepath)[1])
  compress_video(output_video_filepath, output_video_compressed_filepath,
                 output_video_compressed_rate_MB_s*1024*1024*8)
  print('Compression completed in %0.3f seconds' % (time.time() - t0))
  print()
  output_video_filepath = output_video_compressed_filepath

######################################################
# ADD AUDIO TO THE VIDEO
######################################################

if add_audio_track_to_output_video:
  # Open a handle to the newly created composite video.
  output_video_clip = VideoFileClip(output_video_filepath, audio=False)
  
  # Find audio files that overlap with the video.
  print('Searching for audio files that overlap with the composite video')
  audio_clips = []
  for (device_id, media_file_infos) in media_infos.items():
    for filepath in media_file_infos.keys():
      if not is_audio(filepath):
        continue
      # Get the start/end/duration of the audio file.
      audio_filename = os.path.basename(filepath)
      audio_start_time_ms = int(re.search('\d{13}', audio_filename)[0])
      audio_start_time_s = audio_start_time_ms/1000.0
      audio_start_time_s += epoch_offsets_toAdd_s[device_id]
      (audio_rate, audio_data) = wavfile.read(filepath)
      audio_duration_s = (audio_data.shape[0]-1)/audio_rate
      audio_end_time_s = audio_start_time_s + audio_duration_s
      
      audio_clip = None
      # Compute how far into the audio clip the video clip starts.
      # Being negative would imply the audio starts inside video, so the audio start should not be clipped.
      audio_clip_start_offset_s = max(0.0, output_video_start_time_s - audio_start_time_s)
      # Compute the duration of the audio that would align it with the end of the video.
      # Being longer than the audio duration implies the audio ends inside the video, so the audio end should not be clipped.
      audio_clip_duration_s = min(audio_duration_s, (output_video_start_time_s+output_video_duration_s) - audio_start_time_s)
      audio_clip_duration_s -= audio_clip_start_offset_s
      # Load the audio segment if it is valid (if the audio file overlaps with the video).
      if audio_clip_duration_s > 0:
        audio_clip = AudioFileClip(filepath).subclip(t_start=audio_clip_start_offset_s,
                                                           t_end=audio_clip_start_offset_s+audio_clip_duration_s)
        
        # Compute the video time at which this audio clip should start.
        audio_clip_start_time_s = audio_start_time_s + audio_clip_start_offset_s
        audio_video_start_offset_s = audio_clip_start_time_s - output_video_start_time_s
        audio_clip = audio_clip.set_start(audio_video_start_offset_s)
        print('  Found %s spanning [%d, %d] > placed segment [%6.1f, %6.1f] at video time %5ds'
              % (audio_filename, audio_start_time_s, audio_end_time_s,
                 audio_clip_start_offset_s, audio_clip_start_offset_s+audio_clip_duration_s,
                 audio_video_start_offset_s))
        
        # Store the audio clip.
        audio_clips.append(audio_clip)
  
  # Create the composite audio.
  if len(audio_clips) == 0:
    print('  No audio clips were found that overlap with the generated video')
  else:
    print('  Adding %d audio clips to the video' % (len(audio_clips)))
    t0 = time.time()
    composite_audio_clip = CompositeAudioClip(audio_clips)
    composite_audio_clip = composite_audio_clip.volumex(output_audio_track_volume_gain_factor)
    output_video_clip = output_video_clip.set_audio(composite_audio_clip)
    output_video_withAudio_filepath = '%s_withAudio%s' % os.path.splitext(output_video_filepath)
    output_video_clip.write_videofile(output_video_withAudio_filepath,
                                      verbose=False,
                                      logger=proglog.TqdmProgressBarLogger(print_messages=False),
                                      # codec='libx264',
                                      audio_codec='aac',
                                      temp_audiofile='%s.m4a' % os.path.splitext(output_video_filepath)[0],
                                      remove_temp=(not save_audio_track_as_separate_file),
                                      )
    print('Audio track added in %0.3f seconds' % (time.time() - t0))
    print()

######################################################
# EXIT
######################################################

print()
print('Done!')
print()
print()

# Wait until the visualization window is closed.
if show_visualization_window:
  app.exec()












