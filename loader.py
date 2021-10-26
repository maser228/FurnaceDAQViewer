from datetime import datetime
import json
import pandas as pd
import io
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


log_filename = 'C:/Users/mgibson/Desktop/FurnaceDAQ.log'
channel_names = ['Fan', 'Boiler', 'Power', 'Living Room', 'Upstairs Office', 'Basement Bedrooms', 'TV Room', 'DHW']


def run():
    log_data = parse_file(log_filename)  # list of datetime, list-of-bits couples
    last_turn_on = [0, 0, 0, 0, 0, 0, 0, 0]
    total_run_time = [0, 0, 0, 0, 0, 0, 0, 0]
    runs = [ [], [], [], [], [], [], [], [] ]  # lists of start/end couples
    for (timestamp, status) in log_data:
        for cn in range(0, 8):  # channel number
            if last_turn_on[cn] == 0 and status[cn] == 1:
                last_turn_on[cn] = timestamp
            if last_turn_on[cn] and status[cn] == 0:
                run_time = timestamp-last_turn_on[cn]
                print(f'{channel_names[cn]} ran for {run_time}')
                if total_run_time[cn] == 0:
                    total_run_time[cn] = run_time
                else:
                    total_run_time[cn] += run_time
                runs[cn].append((last_turn_on[cn], timestamp))
                last_turn_on[cn] = 0

    # Catch case where something's still on in the last record (power, usually)
    timestamp, status = log_data[-1]
    for cn in range(0, 8):  # channel number
        if last_turn_on[cn] and status[cn] == 1:  # still running
            run_time = timestamp - last_turn_on[cn]
            total_run_time[cn] = run_time
            runs[cn].append((last_turn_on[cn], timestamp))

    print('\nTotals:')
    for cn in range(0, 8):
        print(f'{channel_names[cn]}: {total_run_time[cn]}')
    # if append:
    #     log_data = self.log_data + new_log_data
    # else:
    #     log_data = new_log_data
    print('Done')


    # df = pd.read_csv(io.StringIO(inp), header=None, names=["Task", "Start", "Finish", "Resource"] )
    # df["Diff"] = df.Finish - df.Start

    fig, ax = plt.subplots(figsize=(6, 3))

    labels = []
    for i, channel in enumerate(channel_names):
        labels.append(channel)
        # data = [(r[0].timestamp(), r[1].timestamp() - r[0].timestamp()) for r in runs[i]]
        data = [(r[0], r[1] - r[0]) for r in runs[i]]
        ax.broken_barh(data, (i - 0.4, 0.8), color='crimson')

    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    # ax.set_xlabel("time")
    # plt.xticks(rotation=90)
    fig.autofmt_xdate()
    # ax.fmt_xdata = mdates.DateFormatter('%b %d %I:%M %p') # when you hover over
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d %I:%M %p'))
    # plt.tight_layout()
    plt.show()


def parse_file(filename, append=False, reload=False):
    # if reload = True, we don't want to reset the start time and ideally we wouldn't reset the zoom state either
    print('Processing file...')
    with open(filename, 'r') as log_file:
        log_data = []
        log_file.seek(0)
        for line in log_file:
            try:
                data_in = parse_line(line)
            except Exception as e:
                print('Could not parse line: %s' % line)
                continue  # skip this line and move on
            else:
                log_data.append(data_in)
    return log_data


def parse_line(line):
    splits = str.split(line)
    dt = datetime.strptime(f'{splits[0]} {splits[1]}', '%Y-%m-%d %H:%M:%S')
    bits = json.loads(line[str.find(line, '['):])
    return dt, bits


if __name__ == '__main__':
    run()