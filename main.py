import sys
import os
from PyQt5.QtWidgets import QApplication, QMessageBox, QFileDialog, QSizePolicy
from PyQt5.QtCore import QTimer
import PyQt5.uic
# from PyQt5 import QtCore, QtGui
import json
import math
from datetime import datetime, time
import traceback
from settings import Settings
import matplotlib
from time import perf_counter
matplotlib.use('Qt5Agg')
# import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, MaxNLocator
from mpldatacursor import datacursor


# these are the defaults for settings saved in the registry
default_settings = {'last_used_file': 'c:\\', 'x_axis': 'odo', 'last_used_params': [], 'last_used_events': []}

# the are custom settings for the various quantities plotted.  These are defaults, the user can change them.
per_axis_limits = {'average_speed': (1, 2.5),
                   'stream_angle': (0, 20),
                   'angle_compound': (0, 10),
                   'angle_front': (-10, 10),
                   'angle_side': (-10, 10),
                   'front_angle': (-10, 10),
                   'side_angle': (-10, 10),
                   # 'reservoir_temp': (650, 800),
                   'nozzle_setpoint': (650, 750),
                   # 'nozzle_temp': (650, 750),
                   # 'terminal_temp': (500, 580),
                   'table_temp': (630, 700),
                   # 'temp3': (630, 700),
                   # 'neg_pw': (0, 250),
                   # 'pos_pw': (50, 200),
                   # 'jet_freq': (0, 200),
                   'variance': (-.01, .5),
                   'jitter': (-.01, .1),
                   # 'o2_ppm': (0, 10),
                   'moisture_ppm_in_v': (0, 10),
                   'box_pressure': (0, 5),
                   'pulse_delay': (0, 200),
                   'drop_diam': (380, 410),
                   'drop_diam_calc': (150, 500)
                   }

per_axis_markers = {'drop_diam_calc': ('x', 4),
                    }

default_height = 6  # proportional height of normal plots
per_axis_heights = {'jet_on': 1}

line_styles = {'Triggered camera': ['.80', '-'],
               'Nozzle clean': ['y', '-'],
               'Wire through nozzle orifice': ['y', '-'],
               'Clog': ['r', '-'],
               'Scraped bottom of nozzle face': ['b', '-'],
               'Dross vacuum (manual)': ['g', '-'],
               'Wiped dross from top of reservoir': ['g', '-'],
               'Starting torture test': ['g', '-'],
               'Torture test paused': ['r', '--'],
               'Torture test resumed': ['g', '--'],
               'Aborting torture test': ['r', '-'],
               'Comment': ['k', '-'],
               }

# the following items should not show data for zero values
no_zero_signals = ['average_speed', 'jet_freq', 'pw_neg', 'pw_neg2', 'pw_pos', 'fdRatio', 'efficiency',
                   'stream_phi', 'variance', 'jitter', 'stream_angle', 'jet_curr', 'jet_on',
                   'drop_diam', 'pulse_delay', 'pulse_delay2', 'front_angle', 'side_angle', 'sats_frames',
                   'drop_diam_calc']

only_while_jetting_signals = ['pw_pos', 'pw_neg', 'fdRatio', 'jet_freq', 'average_speed', 'stream_angle',
                              'front_angle', 'side_angle']

forbidden_keys = ['event', 'drop_count', 'date', 'time', 'rate', 'nozzle', 'material', 'operator', 'goal',
                  'other_notes']

key_sets = [['drop_diam', 'drop_diam_calc'],
            ['nozzle_setpoint', 'nozzle_temp']]  # for future use, forces keys into one chart

# these often have unique data appended so need to be stripped for use in the UI event list
shortened_events = ['Triggered camera', 'Starting torture test', 'Aborting torture test', 'Completed cycle',
                    'Torture test completed']

# the following get their own graphs so they don't need to show up in the UI event list
special_plots = {'Nozzle service': ['Nozzle purge', 'Nozzle service: wipe', 'Move to wipe position',
                                    'Wiped dross from top of reservoir',
                                    'Scraped bottom of nozzle face', 'Dross vacuum (manual)',
                                    'Nozzle service: weigh drops', 'Nozzle service: free jet'],
                 'Torture test': ['Torture test paused', 'Torture test resumed', 'Aborting torture test',
                                  'Starting torture test', 'Torture test completed'],
                 'Comments/videos': ['Comment', 'Triggered camera'],
                 'Selected Events': []  # filled in later
                 }


class MHDLogView(QApplication):
    def __init__(self):
        QApplication.__init__(self, sys.argv)
        settings = Settings("Desktop Metal", "MHD Log View", default_settings)
        self.ui = UI(settings=settings)
        sys.excepthook = self.exception_handler  # Qt apps don't give any info otherwise

    @staticmethod
    def main():
        mhd = MHDLogView()
        mhd.run()

    def run(self):
        self.ui.win.show()  # Show the UI
        self.ui.run()  # Execute the UI run script
        self.exec_()

    @staticmethod
    def exception_handler(exception_type, exception_value, exception_traceback):
        # this is called because of the 'sys.excepthook = self.exception_handler' statement in __init__
        try:
            exception_str = ''.join(traceback.format_exception(exception_type, exception_value, exception_traceback))
            print(exception_str)
        except Exception:
            exception_str = ''.join(traceback.format_exc())
            print(exception_str)
            raise
        finally:
            sys.exit(1)


class GraphInit(FigureCanvas):
    def __init__(self, parent=None):
        fig = Figure()
        self.axes = fig.add_subplot(111)
        self.axes.grid()
        super().__init__(fig)
        self.setParent(parent)
        # self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        # self.updateGeometry()


class UI(object):
    def __init__(self, settings=None):
        ui_path = os.path.dirname(os.path.realpath(__file__))
        self.win = PyQt5.uic.loadUi(ui_path + '\\mhdlogviewGUI.ui')
        # self.filename = ui_path + '\\testJSON.txt'
        self.settings = settings
        self.plotWin = GraphInit(self.win.plotWidget)
        self.win.plotWidget.layout().addWidget(self.plotWin)
        self.navBar = NavigationToolbar(self.plotWin, None)
        self.win.plotWidget.layout().addWidget(self.navBar)

        self.log_data = []  # what's in the file
        self.info = None  # nozzle, material, etc.
        self.signal_keys = []  # non-duplicate list of keys appearing in the log
        self.event_list = []  # non-duplicate list of events that appear in the log
        self.comment_indices = []  # list of indexes that contain a comment
        self.comment_list = []  # list of the actual comment texts
        self.plot_data = []  # what we're actually plotting based on user selections
        self.plot_data_times = []
        self.start_time = None  # a datetime representing start of run, used for x-axis

        self.filename = self.settings.value('last_used_file')

        self.win.timer = QTimer()
        self.win.timer.timeout.connect(self.reload_log_file)

    def run(self):
        self.init_ui()  # get initial values from the controllers
        self.attach_ui_connections()
        self.win.timer.start(20000)  # used for auto-update

    def init_ui(self):
        w = self.win
        w.txtLogFilename.setText('Please select a log file to load')
        # w.txtLogFilename.setText(self.filename.split('/')[-1])  # just the file (no path)

    def attach_ui_connections(self):
        w = self.win
        w.btnLogFileDialog.pressed.connect(self.file_dialog)
        w.refreshPlotButton.pressed.connect(self.refresh_plot)
        w.listComments.clicked.connect(self.comment_click)

    def file_dialog(self):
        path = self.filename
        filename, _ = QFileDialog.getOpenFileName(None, 'Select Log File', path,
                                                  "Text Files (*.txt);;All Files (*.*)")
        if not filename:
            return

        print(f'Opening {filename}')
        self.settings.setValue('last_used_file', filename)
        self.filename = filename
        self.settings.setValue('last_filename', filename)
        self.win.txtLogFilename.setText(filename)
        self.win.txtLogFilename.setToolTip(filename)

        self.load_log_file(filename)

    def load_log_file(self, filename, reload=False):
        append = self.win.chkAppend.isChecked()
        self.process_file(filename, append, reload)
        self.add_calculated_values()
        self.update_ui()

    def reload_log_file(self):
        if not self.filename or not self.win.chkAutoUpdate.isChecked():
            return
        self.load_log_file(self.filename, reload=True)

    def process_file(self, filename, append=False, reload=False):
        # if reload = True, we don't want to reset the start time and ideally we wouldn't reset the zoom state either
        print('Processing file...')
        new_log_data = self.read_file_by_line(filename)
        if append:
            self.log_data = self.log_data + new_log_data
        else:
            self.log_data = new_log_data

        # at this point, log_data should be a List of Dicts -- one for each entry
        if self.log_data[0].get('nozzle', None):
            self.info = self.log_data[0]  # collects the metadata for use later

        # get the start time -- it's the first time entry in the file
        # (break below means we stop at the first date we find)
        for line in self.log_data:
            if 'time' in line and 'date' in line:
                first_time = line['time']
                first_date = line['date']
                try:
                    # 24-hour format
                    self.start_time = datetime.strptime(first_time, '%H:%M:%S').time()
                except ValueError:
                    # 12-hour AM/PM format
                    self.start_time = datetime.strptime(first_time, '%I:%M:%S %p').time()
                start_date = datetime.strptime(first_date, '%Y%m%d').date()
                start_datetime = datetime.combine(start_date, self.start_time)
                end_datetime = datetime.combine(start_date, time().max)
                if not reload and not append:
                    self.win.dateTimeMin.setDateTime(start_datetime)
                    self.win.dateTimeMax.setDateTime(end_datetime)
                break

        # parse file and retrieve keys, events, comment_indices
        signal_keys = []
        event_list = []
        comments = []
        for line_num, line in enumerate(self.log_data):
            # Generate the list of signals
            for key in line:
                if key not in signal_keys and key not in forbidden_keys:
                    signal_keys += [key]
            # Process events:
            event = line.get('event')
            if event:
                if "Comment:" in event:  # comments are moved to the comment list
                    comments += [line_num]
                    line['event_type'] = "Comment"
                else:
                    for e in shortened_events:  # condense events
                        if e in event:
                            event_type = e
                            break
                    else:
                        event_type = event
                    line['event_type'] = event_type

                    # omit any events from the list that have their own subplot -- DISABLED WITH PASS
                    for e in [x for v in special_plots.values() for x in v]:  # flattens the list of dict values
                        if e in event:
                            pass
                            # break
                    else:
                        if event_type not in event_list:
                            event_list += [event_type]
        # comments:
        self.comment_indices = comments  # used for lookup if user clicks comment in listbox
        comment_list = []
        for index in comments:
            comment_list += [self.log_data[index]['event'][9:]]

        self.comment_list = comment_list
        self.event_list = sorted(event_list)
        self.signal_keys = sorted(signal_keys)

    def add_calculated_values(self):
        if 'fdRatio' in self.signal_keys and 'drop_diam' not in self.signal_keys:
            self.signal_keys += ['drop_diam']
            for num, line in enumerate(self.log_data):
                if 'fdRatio' in line:
                    line['drop_diam'] = diam_from_volume(line['fdRatio'])
                if line.get('event', None) and 'Triggered camera' in line['event']:
                    # example: "Triggered camera, filename: 20180703-110254"
                    fn = line['event'][28:]  # extracts filename
                    # need to get speed from previous entry because illuminator stops nanny
                    sp = self.log_data[num-1].get('average_speed', None)
                    if sp == 0 or sp is None:
                        sp = self.log_data[num-2].get('average_speed', None)
                    freq = line['jet_freq']
                    print('%s, %s, %s' % (fn, freq, sp))

    def update_ui(self):
        # update the UI
        event_list = self.event_list
        comment_list = self.comment_list
        signal_keys = self.signal_keys
        w = self.win
        w.listEvents.clear()
        w.listEvents.addItems(event_list)
        w.listComments.clear()
        w.listComments.addItems(comment_list)
        w.signalListWidget.clear()
        w.signalListWidget.addItems(signal_keys)

        # select the last-used signals, if present
        for key in self.settings.value('last_used_params'):
            if key in signal_keys:
                for item in self.win.signalListWidget.findItems(key, PyQt5.QtCore.Qt.MatchExactly):
                    item.setSelected(True)

        # select last-used events, if present
        for key in self.settings.value('last_used_events'):
            if key in event_list:
                for item in self.win.listEvents.findItems(key, PyQt5.QtCore.Qt.MatchExactly):
                    item.setSelected(True)

        self.refresh_plot()

    # @staticmethod
    # def read_file(log_text):
    #     # Note: This will never work because it only works on one JSON and our file has one for each line
    #     log_text.seek(0)  # go to beginning of file
    #     log_data = json.loads(log_text.read())
    #     return log_data

    @staticmethod
    def read_file_by_line(filename):
        log_file = open(filename, 'r')
        log_data = []
        log_file.seek(0)
        for line in log_file:
            try:
                data_in = json.loads(line)
            except:
                print('Could not process line: %s' % line)
                continue  # skip this line and move on
            else:
                log_data.append(data_in)
        log_file.close()
        return log_data

    def refresh_plot(self):
        # filename = self.filename
        time_base = self.win.btnTimeBase.isChecked()

        # Make sure that a logfile has been loaded
        if self.log_data is None:
            msg = QMessageBox()
            msg.setText('No file loaded')
            msg.exec()
            return

        # Read signals user wants to plot
        desired_plots = [x.text() for x in self.win.signalListWidget.selectedItems()]  # Extract text names from list of QObjects
        if not desired_plots:
            msg = QMessageBox()
            msg.setText('No signals selected')
            msg.exec()
            return
        self.settings.setValue('last_used_params', desired_plots)  # save the plots for next time

        # Find which events to show
        desired_events = [x.text() for x in self.win.listEvents.selectedItems()]
        special_plots['Selected Events'] = desired_events
        self.settings.setValue('last_used_events', desired_events)  # save the plots for next time

        # Read out user options
        skip_no_data = self.win.chkSkipNoData.isChecked()
        skip_no_jetting = self.win.chkSkipNoJetting.isChecked()

        # Refresh the plot with desired signals
        # print('Refreshing plot!')
        self.plotWin.figure.clf()

        self.generate_plot_data(desired_plots, skip_no_data, skip_no_jetting)

        if self.plot_data:
            self.generate_plot(desired_plots, time_base)

    def generate_plot_data(self, desired_plots, skip_no_data=False, skip_no_jetting=False):
        # make a list called 'plot_data' which contains only the data needed, with null placeholders
        print('Generating plot data.')
        self.plot_data = []
        self.plot_data_times = []
        index = 0
        # TODO: speed this section up
        min_date_time = self.win.dateTimeMin.dateTime().toPyDateTime()
        max_date_time = self.win.dateTimeMax.dateTime().toPyDateTime()
        for num, line in enumerate(self.log_data):
            # bring in the x-axis data
            date_time_string = line.get('date', '') + ' ' + line.get('time', '')
            if len(date_time_string) == 1:  # no date/time data in this record --> ignore
                continue
            try:
                date_time = datetime.strptime(date_time_string, '%Y%m%d %H:%M:%S')  # convert to datetime type
            except ValueError:
                date_time = datetime.strptime(date_time_string, '%m/%d/%Y %I:%M:%S %p')
            # filter out values not within the requested range
            if not min_date_time < date_time < max_date_time:
                continue
            time_as_num = matplotlib.dates.date2num(date_time)  # convert to number of days since epoch (for scale)
            newline = {'event': line.get('event'), 'event_type': line.get('event_type'),
                       # 'time': datetime.strptime(line['time'], '%H:%M:%S'),  # - self.start_time,
                       'time': time_as_num,
                       'odo': line.get('odo'),
                       'drop_count': line.get('drop_count')}
            # bring in user-selected data
            if skip_no_data:
                data_present = False  # flag so we don't include rows with no data
            else:
                data_present = True  # will always cause all rows to be included
            for item in desired_plots:
                value = line.get(item, None)
                data_present = data_present or value  # one valid datum will set/leave this true
                if item in only_while_jetting_signals:
                    if value:
                        value = value * line.get('jet_on', 1)  # don't show when not jetting
                    else:
                        value = None
                if item in no_zero_signals and value == 0:
                    value = None
                if item not in ['event', 'time', 'odo', 'drop_count']:  # don't rewrite data already there
                    newline[item] = value
            # check for no jetting switch
            if skip_no_jetting and not line.get('jet_on'):
                data_present = False
            # check for no data
            if line.get('event'):  # always show any event
                data_present = True
            if data_present:
                newline['index'] = index
                index += 1
                self.plot_data.append(newline)
                self.plot_data_times.append(time_as_num)

    def generate_plot(self, desired_plots, time_base=True):
        print('Generating plot...')
        # axis = object representing a lane in the graph shown to the user, usually contains one plot,
        #        generated by the .subplot() routine below
        # plot = a single parameter

        # Go through the desired plots and make a list, combining as needed
        drop_diam_axis = None
        axes = []  # format: [[matplotlib axis], [plot1, plot2], height, [limits]]
        for n, plot in enumerate(desired_plots):
            # TODO: get rid of this kludge and make general solution for combined plots
            if plot == 'drop_diam' or plot == 'drop_diam_calc':
                if drop_diam_axis is not None:
                    axes[drop_diam_axis][1].append(plot)
                    continue  # skip making a new list item since we're just adding to an existing one
                else:
                    drop_diam_axis = n  # remember which plot has drop_diam (could be this one)
            height = per_axis_heights.get(plot, default_height)
            limits = per_axis_limits.get(plot)
            axes.append([None, [plot], height, limits])
        for _ in special_plots:
            axes.append([None, [], 1, None])  # for selected events

        # Create an axis set with required number of subplots:
        num_plots = len(axes)
        height_ratios = [x[2] for x in axes]

        subplots = self.plotWin.figure.subplots(nrows=num_plots,
                                                gridspec_kw={'height_ratios': height_ratios},
                                                sharex=True)
        for n, axis in enumerate(axes):
            axis[0] = subplots[n]  # put the subplot object into the first position of each row in axes

        # Populate the user's axes
        print('Adding user axes...')
        for axis in axes[:-len(special_plots)]:
            for plot in axis[1]:  # list of plot names for this axis, usually only one
                marker, marker_size = per_axis_markers.get(plot, ('.', 1))
                if time_base:
                    func = axis[0].plot_date
                    x_data = [line['time'] for line in self.plot_data]
                else:
                    func = axis[0].plot
                    x_data = [line['index'] for line in self.plot_data]
                y_data = [line[plot] for line in self.plot_data]
                func(x_data, y_data, linestyle='-', linewidth=1, marker=marker, markersize=marker_size, label=plot)
            if axis[3]:  # y limits
                axis[0].set_ylim(axis[3])
            label = axis[1][0].replace('_', '\n')  # Replace underscores with line breaks
            axis[0].set(ylabel=label)  # whatever the first plot is
            axis[0].grid(which='both')

        # add special plots
        for num, plot in enumerate(special_plots):
            # add the axis for user-selected events
            print('Adding %s event plot...' % plot)
            axis = axes[-(num+1)][0]
            axis_limits = axis.get_ylim()
            for line in self.plot_data:
                ev = line.get('event_type')
                # only include items selected in the list
                if False:  # special case for user events:  plot == 'Selected Events':
                    criteria = ev and ev in list()
                else:
                    # criteria = ev and ev in list(set(special_plots[plot]) & set(special_plots['Selected Events']))
                    criteria = ev and ev in special_plots[plot]
                if criteria:
                    if time_base:
                        line_time = line['time']  # matplotlib.dates.date2num(line['time'])
                    else:
                        line_time = line['index']
                    line_formats = line_styles.get(ev, ['k', '-'])
                    line_color, line_style = line_formats
                    date_time = matplotlib.dates.num2date(line_time)
                    nice_time = datetime.strftime(date_time, '%H:%M:%S')
                    label = '%s\n%s\n%s' % (line.get('event'), nice_time, line.get('drop_count'))
                    axis.vlines(line_time, axis_limits[0], axis_limits[1],
                                colors=line_color, label=label, linestyles=line_style)
            axis.set_ylabel(plot, rotation=0, size='xx-small')
            y = axis.get_yaxis()
            y.set_visible(True)
            y.set_major_formatter(FuncFormatter(self.null_format_fn))  # gets rid of numbers
            y.set_tick_params(which='both', left='off')
            if num == 0:  # put the formatter on the last plot
                axis.get_xaxis().set_major_formatter(FuncFormatter(self.format_fn))
                axis.get_xaxis().set_major_locator(MaxNLocator(integer=True))

        # add the pop-up balloons when you click
        # TODO: find out why this calls the formatter many times for each subplot every time you click, and also when you dismiss the balloon
        # for regular plots:
        regular_plot_axes = subplots[:-(len(special_plots))]
        datacursor(hover=False, axes=regular_plot_axes, display='single', draggable=False,
                   formatter=self.datacursor_formatter)
        # for special plots, all in info is in the label:
        special_plot_axes = subplots[-(len(special_plots)):]
        datacursor(hover=False, axes=special_plot_axes, display='single', draggable=False,
                   formatter='{label}'.format)

        # Add title and spacing, and draw figure
        i = self.info
        if i:
            title_text = (
                'Nozzle: %s   Material: %s   Operator: %s   Goal: %s   Notes: %s \n' % (
                    i.get('nozzle'), i.get('material'),
                    i.get('operator'), i.get('goal'),
                    i.get('other notes')))
        else:
            title_text = ''
        self.plotWin.figure.suptitle(title_text)

        # gets the spacing right...ish
        self.on_resize()
        self.plotWin.figure.canvas.mpl_connect('resize_event', self.on_resize)

        print('Drawing plot...')
        self.plotWin.draw()
        print('Done')

    def on_resize(self, *args):
        # subplots_adjust using a percentage of the size, so get the size first
        figure_width = self.plotWin.figure.get_figwidth()
        self.plotWin.figure.subplots_adjust(left=.8/figure_width, right=.98, top=0.95, bottom=0.08, hspace=.02)

    def comment_click(self):
        cl = self.win.listComments
        if cl.selectedItems():
            # comment_text = cl.selectedItems().pop().text()
            index = self.comment_indices[cl.currentRow()]
            line = self.log_data[index]
            self.win.lblCommentInfo.setText('%s %s  Odo: %s   Drop Count: %s' %
                                            (line['date'], line['time'], line['odo'], line['drop_count']))

    @staticmethod
    def datacursor_formatter(**kwargs):
        # artist = kwargs['event'].artist
        # print(artist)
        x = kwargs['x']
        y = kwargs['y']
        date_time = matplotlib.dates.num2date(x)
        nice_time = datetime.strftime(date_time, '%H:%M:%S')
        return '%s = %s\n%s\n%s' % (kwargs['label'], y, nice_time, 'drops')

    def format_fn(self, tick_val, tick_pos):
        # format function; used to make custom x-axis labels
        if self.win.btnTimeBase.isChecked():  # time-based plot, tick_val will be a time in days since epoch
            # find closest entry to the tick mark's time
            # TODO: this takes .01 - 7 sec and leaks memory -- can it be more efficient?
            # TODO: maybe if we force the tick marks to be exact we don't need this
            # then = time.perf_counter()
            # index, closest_time = min(enumerate([line['time'] for line in self.plot_data]), key=lambda x: abs(x[1] - tick_val))
            # time1 = time.perf_counter() - then
            then = perf_counter()
            index, closest_time = min(enumerate([t for t in self.plot_data_times]), key=lambda x: abs(x[1] - tick_val))
            time2 = perf_counter() - then
            # print(tick_val, time2)
            error_sec = abs(tick_val - self.plot_data[index]['time']) * 3600 * 24
            if error_sec > 2:  # don't grab data that's off by more than two seconds
                date_time = matplotlib.dates.num2date(tick_val)
                return datetime.strftime(date_time, '%H:%M')
        else:  # index-based plot, tick_val will be the data log entry number
            index = int(tick_val)
        if index and 0 <= index <= len(self.plot_data):
            line = self.plot_data[index]
            # et = datetime.strptime(line['time'], '%H:%M:%S') - self.start_time
            date_time = matplotlib.dates.num2date(line['time'])
            closest_time = datetime.strftime(date_time, '%H:%M:%S')
            return '%s\n %s\n %s' % (closest_time, line['odo'], line['drop_count'])
        else:
            return ''

    @staticmethod
    def null_format_fn(*args):
        return ''


def diam_from_volume(drop_volume_nl):
    """returns drop diameter in microns given drop volume in nL"""
    drop_volume_mm3 = drop_volume_nl / 1000
    drop_diam_um = round(1000 * ((drop_volume_mm3/(4/3*math.pi))**(1/3))*2)  # x1000 for microns
    return drop_diam_um


if __name__ == '__main__':
    MHDLogView.main()
