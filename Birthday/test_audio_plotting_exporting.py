

from scipy.io import wavfile
from scipy import signal
from scipy import interpolate

import os
import re
import numpy as np
import time

import cv2
import pyqtgraph
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
from pyqtgraph.Qt.QtGui import QPixmap, QImage

from helpers import *

use_waveform = True
use_spectrogram = False
only_plot_one_test = False

data_dir_root = 'C:/Users/jdelp/Desktop/_whale_birthday_s3_data'

filepath = os.path.join(data_dir_root, 'DSWP-KASHMIR_MIXPRE6-1',
                              'CETI23-281.1688831930000.WAV')

num_audio_channels = 1
audio_pens = [pyqtgraph.mkPen([255, 255, 255], width=1),
              pyqtgraph.mkPen([255, 0, 255], width=1)]

audio_resample_rate_hz = 9600 # original rate is 96000
audio_plot_duration_beforeCurrentTime_s = 5
audio_plot_duration_afterCurrentTime_s  = 10

audio_plot_length_beforeCurrentTime = int(audio_resample_rate_hz * audio_plot_duration_beforeCurrentTime_s)
audio_plot_length_afterCurrentTime = int(audio_resample_rate_hz * audio_plot_duration_afterCurrentTime_s)
audio_plot_length = 1 + audio_plot_length_beforeCurrentTime + audio_plot_length_afterCurrentTime
audio_timestamps_toPlot_s = np.arange(start=0, stop=audio_plot_length)/audio_resample_rate_hz - audio_plot_duration_beforeCurrentTime_s



filename = os.path.basename(filepath)
start_time_ms = int(re.search('\d{13}', filename)[0])
start_time_s = start_time_ms/1000.0
# start_time_s += epoch_offsets_toAdd_s[device_id]




(audio_rate, audio_data) = wavfile.read(filepath)
num_samples = audio_data.shape[0]
timestamps_s = start_time_s + np.arange(start=0, stop=num_samples)/audio_rate
# Resample the data.
num_samples = audio_data.shape[0]
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
audio_data = audio_data_resampled
timestamps_s = timestamps_s_resampled

print('loaded')

if only_plot_one_test and use_waveform:
  app = QtWidgets.QApplication([])
  start_index = int(160*audio_resample_rate_hz) - audio_plot_length_beforeCurrentTime
  end_index = int(160*audio_resample_rate_hz) + audio_plot_length_afterCurrentTime
  pyqtgraph.plot(np.array(range(start_index, end_index))/audio_resample_rate_hz, audio_data[start_index:end_index, 0])
  app.exec()
  import sys
  sys.exit()

if only_plot_one_test and use_spectrogram:
  t0 = time.time()
  start_index = int(160*audio_resample_rate_hz) - audio_plot_length_beforeCurrentTime
  end_index = int(160*audio_resample_rate_hz) + audio_plot_length_afterCurrentTime
  print(audio_data[start_index:end_index,0].shape)
  f, t, Sxx = signal.spectrogram(audio_data[start_index:end_index,0], audio_resample_rate_hz,
                                 window=signal.get_window('tukey', int(0.1*audio_resample_rate_hz)),
                                 nperseg=None)
  print('spectogram creation duration', time.time() - t0)
  print('t shape', t.shape)
  print('f shape', f.shape)
  # print(np.amin(Sxx), np.amax(Sxx))
  # print('2')
  # app = QtWidgets.QApplication([])
  # win = pyqtgraph.GraphicsLayoutWidget()
  # p1 = win.addPlot()
  # img = pyqtgraph.ImageItem()
  # p1.addItem(img)
  # # hist = pyqtgraph.HistogramLUTItem()
  # # hist.setImageItem(img)
  # # win.addItem(hist)
  # win.show()
  # # hist.setLevels(np.min(Sxx), np.max(Sxx))
  # # hist.gradient.restoreState(
  # #     {'mode': 'rgb',
  # #      'ticks': [(0.5, (0, 182, 188, 255)),
  # #                (1.0, (246, 111, 0, 255)),
  # #                (0.0, (75, 0, 113, 255))]})
  # img.setImage(Sxx)
  # # img.scale(t[-1]/np.size(Sxx, axis=1),
  # #           f[-1]/np.size(Sxx, axis=0))
  # p1.setLimits(xMin=0, xMax=t[-1], yMin=0, yMax=f[-1])
  # p1.setLabel('bottom', "Time", units='s')
  # p1.setLabel('left', "Frequency", units='Hz')
  # app.exec()
  
  
  # app = QtWidgets.QApplication([])
  # win = pyqtgraph.GraphicsLayoutWidget()
  # h_plot = win.addPlot()
  # h_heatmap = pyqtgraph.ImageItem(image=Sxx, hoverable=False)
  # # Transpose since the image is indexed as (x, y) but numpy as (y, x).
  # # Flip so y=0 is at the top of the heatmap.
  # # h_plot.setLimits(xMin=0, xMax=t[-1], yMin=0, yMax=f[-1])
  # h_plot.addItem(h_heatmap, title='yay')
  # # h_plot.hideAxis('bottom')
  # # h_plot.hideAxis('left')
  # h_plot.getAxis('bottom').setLabel('Horizontal Index')
  # h_plot.getAxis('right').setLabel('Vertical Index')
  # h_plot.setAspectLocked(True)
  # h_colorbar = h_plot.addColorBar(h_heatmap, colorMap='inferno', interactive=True)
  # # Note that the below seems needed to update the heatmap, even if the levels stayed the same.
  # t0 = time.time()
  # h_heatmap.setImage(np.flipud(Sxx).T)
  # h_colorbar.setLevels([0, 150])
  # h_heatmap.setRect(pyqtgraph.QtCore.QRectF(6, 9, 1000, 3000))
  # h_plot.setLimits(xMin=6, xMax=1006, yMin=9, yMax=3009)
  # print('heatmap update', time.time() - t0)
  # win.show()
  # app.exec()
  
  app = QtWidgets.QApplication([])
  win = pyqtgraph.GraphicsLayoutWidget()
  h_plot = win.addPlot()
  h_heatmap = pyqtgraph.ImageItem(image=Sxx, hoverable=False)
  h_plot.addItem(h_heatmap, title='yay')
  h_plot.showAxis('bottom')
  h_plot.showAxis('left')
  h_plot.getAxis('bottom').setLabel('Time [s]')
  h_plot.getAxis('left').setLabel('Frequency [kHz]')
  # h_plot.setAspectLocked(True)
  f_ticks = [(tick_index, '%0.1f' % (f_label/1000)) for (tick_index, f_label) in enumerate(f)]
  t_ticks = [(tick_index, '%0.1f' % t_label) for (tick_index, t_label) in enumerate(t)]
  h_colorbar = h_plot.addColorBar(h_heatmap, colorMap='inferno', interactive=True)
  t0 = time.time()
  h_heatmap.setImage(np.flipud(Sxx).T)
  h_colorbar.setLevels([np.quantile(Sxx, 0), np.quantile(Sxx, 1)])
  h_plot.getAxis('left').setTicks([f_ticks[::1000]])
  h_plot.getAxis('bottom').setTicks([t_ticks[::40]])
  QtCore.QCoreApplication.processEvents()
  print('heatmap', time.time() - t0)
  win.show()
  app.exec()
  
  # import matplotlib.pyplot as plt
  # plt.pcolormesh(t, f, Sxx)
  # plt.ylabel('Frequency [Hz]')
  # plt.xlabel('Time [sec]')
  # plt.colorbar()
  # plt.show()

  import sys
  sys.exit()

app = QtWidgets.QApplication([])
graphics_layout = pyqtgraph.GraphicsLayoutWidget()
grid_layout = QtWidgets.QGridLayout()
graphics_layout.setLayout(grid_layout)

layout_specs = (4, 0, 1, 4)
composite_layout_column_width = 50
composite_layout_column_height = composite_layout_column_width/(1+7/9)

audio_plotWidget = pyqtgraph.PlotWidget()
grid_layout.addWidget(audio_plotWidget, *layout_specs, alignment=pyqtgraph.QtCore.Qt.AlignmentFlag.AlignCenter)
grid_layout.setRowMinimumHeight(layout_specs[0], composite_layout_column_height)
audio_plotWidget.setMinimumWidth(composite_layout_column_width*layout_specs[3])
random_audio = np.random.rand(audio_plot_length, 2)
if use_waveform:
  h_lines = []
  for channel_index in range(num_audio_channels):
    h_lines.append(audio_plotWidget.plot(audio_timestamps_toPlot_s, random_audio[:,channel_index],
                                         pen=audio_pens[channel_index]))
  h_lines.append(audio_plotWidget.plot([0, 0], [-500, 500], pen=pyqtgraph.mkPen([0, 150, 150], width=7)))
if use_spectrogram:
  pass

graphics_layout.setWindowTitle('Happy Birthday!')
# graphics_layout.show()


def update_layout_widget(layout_widget, layout_specs, data, label=None):
  if use_waveform:
    # Update the line items with the new data.
    for channel_index in range(num_audio_channels):
      layout_widget[channel_index].setData(audio_timestamps_toPlot_s, data[:,channel_index])
    # Plot a vertical current time marker, and update the y range.
    if np.amax(data) < 50:
      layout_widget[-1].setData([0, 0], np.amax(data)*np.array([-50, 50]))
      audio_plotWidget.setYRange(-50, 50) # avoid zooming into an empty plot
    else:
      layout_widget[-1].setData([0, 0], np.amax(data)*np.array([-1, 1]))
      audio_plotWidget.enableAutoRange(enable=0.9) # allow automatic scaling that shows 90% of the data
  if use_spectrogram:
    pass








data_index = int(160*audio_resample_rate_hz) #int(audio_data.shape[0]*0.1)
data_index_increment = audio_resample_rate_hz/10
data = audio_data

N = 20
t0 = time.time()
for n in range(N):
  data_index = int(data_index + data_index_increment)

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
  # Update the subplot with the waveform segment.
  update_layout_widget(h_lines, layout_specs, data_toPlot)

  QtCore.QCoreApplication.processEvents()

  img = graphics_layout.grab().toImage()
  img = qimage_to_numpy(img)
  img = np.array(img[:,:,0:3])
  cv2.imshow('test', img)
  cv2.waitKey(1)

duration_s = time.time() - t0
print()
print('duration: %0.3f s' % (duration_s))
print('duration per loop: %0.3f s' % (duration_s/N))
print('loop rate: %0.3f Hz' % (N/duration_s))
print()

# app.exec()