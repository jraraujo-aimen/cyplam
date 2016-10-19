import cv2
import numpy as np
import pandas as pd

from measures.velocity import Velocity
from measures.geometry import Geometry


def serialize_frame(frame, encode='*.png'):
    return cv2.imencode(encode, frame)[1].tostring(None)


def deserialize_frame(string):
    return cv2.imdecode(
        np.fromstring(string, dtype=np.uint8), cv2.CV_LOAD_IMAGE_UNCHANGED)


def read_frames(frames):
    return np.array([deserialize_frame(frame) for frame in frames])


def write_hdf5(filename, data, keys=None):
    store = pd.HDFStore(filename, complevel=9, complib='blosc')
    if keys is None:
        keys = data.keys()
    for key in keys:
        store.put(key, data[key], format='table', append=False)
    store.close()


def read_hdf5(filename, keys=None):
    store = pd.HDFStore(filename)
    if keys is None:
        keys = [key[1:] for key in store.keys()]
    data = {}
    for key in keys:
        data[key] = store.get(key)
    store.close()
    return data


def append_data(dataframe, data):
    for key, value in data.iteritems():
        dataframe[key] = pd.Series(value, index=dataframe.index)
    return dataframe


def calculate_velocity(time, position):
    velocity = Velocity()
    data = {'speed': [], 'velocity': [], 'running': []}
    for k in range(len(position)):
        speed, vel = velocity.instantaneous(time[k], np.array(position[k]))
        data['speed'].append(speed)
        data['velocity'].append(vel)
        data['running'].append(speed > 0.0005)
    return data


def calculate_geometry(frames, thr=200):
    geometry = Geometry(thr)
    ellipses = [geometry.find_geometry(frame) for frame in frames]
    data = {'x': [], 'y': [], 'height': [], 'width': [], 'angle': []}
    data['x'] = np.array([ellipse[0][0] for ellipse in ellipses])
    data['y'] = np.array([ellipse[0][1] for ellipse in ellipses])
    data['height'] = np.array([ellipse[1][0] for ellipse in ellipses])
    data['width'] = np.array([ellipse[1][1] for ellipse in ellipses])
    data['angle'] = np.array([ellipse[2] for ellipse in ellipses])
    return data


def calculate_maximum(images):
    data = images.reshape((len(images), -1))
    maximums = np.max(data, axis=1)
    return {'maximum': maximums}


def find_laser_switch(laser):
    lasernr = np.append(np.bitwise_not(laser[0]), np.bitwise_not(laser[:-1]))
    lasernl = np.append(np.bitwise_not(laser[1:]), np.bitwise_not(laser[-1]))
    laser_on = np.bitwise_and(laser, lasernr)
    laser_off = np.bitwise_and(laser, lasernl)
    return laser_on, laser_off


def find_tracks(tachyon, meas='minor_axis', thr=0):
    tachyonw = tachyon[tachyon[meas].notnull()]
    laser = np.array(tachyonw[meas] > thr)
    laser_on, laser_off = find_laser_switch(laser)
    lon_idx = tachyonw.index[laser_on]
    loff_idx = tachyonw.index[laser_off]
    tracks = []
    for k in range(len(lon_idx)):
        if loff_idx[k] - lon_idx[k] > 30:
            tracks.append([tachyon['time'][lon_idx[k]],
                           tachyon['time'][loff_idx[k]]])
    return tracks


def find_indexes_track(data, track, offset=0):
    time0, time1 = track
    idx0 = data.index[data.time < time0-offset][-1]
    idx1 = data.index[data.time > time1+offset][0]
    if idx0 < 0:
        idx0 = 0
    if idx1 > len(data):
        idx1 = len(data)
    return idx0, idx1


def find_data_tracks(data, tracks, offset=1.0):
    if type(tracks[0]) is list:
        time0 = tracks[0][0]
        time1 = tracks[-1][1]
    else:
        time0 = tracks[0]
        time1 = tracks[1]
    idx0, idx1 = find_indexes_track(data, [time0, time1], offset)
    return data.loc[idx0:idx1]


def calculate_back(tachyon):
    back = {'digital_level': []}
    for frame in tachyon.frame:
        img = deserialize_frame(frame)
        back['digital_level'].append(np.mean(img[25:27, 25:27]))
    print max(back['digital_level'])
    return back


def calculate_clad(tachyon):
    data = {'digital_level': []}
    for frame in tachyon.frame:
        img = deserialize_frame(frame)
        data['digital_level'].append(np.mean(img[15:18, 11:13]))
    print max(data['digital_level'])
    return data


def calculate_maximun(tachyon):
    data = {'digital_level': []}
    for frame in tachyon.frame:
        img = deserialize_frame(frame)
        data['digital_level'].append(img.max())
    print max(data['digital_level'])
    return data


# TODO: Move to ellipse calculation
def resize_ellipse(scale, img, ellipse):
    img = cv2.resize(img, (scale*32, scale*32))
    ((x, y), (w, l), a) = ellipse
    ellipse = ((scale*x, scale*y), (scale*w, scale*l), a)
    return img, ellipse


if __name__ == "__main__":
    import os
    import plot
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-f', '--file', type=str, default=None, help='hdf5 or bag filename')
    parser.add_argument(
        '-t', '--tables', type=str, default=None, nargs='+', help='tables names')
    args = parser.parse_args()

    if args.file:
        name, ext = os.path.splitext(args.file)
        if ext == '.bag':
            import bag2h5
            data = bag2h5.read_bag_data(args.file)
            bag2h5.write_hdf5(name + '.h5', data)
        else:
            filename = args.file
            tables = args.tables
            data = read_hdf5(filename, tables)

    if 'robot' in data.keys():
        robot = data['robot']
        velocity = calculate_velocity(robot.time, robot.position)
        robot = append_data(robot, velocity)
        plot.plot_speed(robot)

    if 'tachyon' in data.keys():
        tachyon = data['tachyon']
        tachyon = tachyon[tachyon.frame.notnull()]

        if 'minor_axis' in tachyon.columns:
            tachyon = tachyon[tachyon.minor_axis.notnull()]
            plot.plot_data(tachyon, ['time'], ['minor_axis'], ['blue'])

            tracks = find_tracks(tachyon, meas='minor_axis')  # first track (laser on, laser off)
            frames = read_frames(find_data_tracks(tachyon, tracks, offset=0).frame)
            plot.plot_frames(frames)

            if 'temperature' in tachyon.columns:
                plot.plot_temperature(tachyon)

            if 'power' in tachyon.columns:
                plot.plot_power(tachyon[tachyon.power.notnull()])
        else:
            frames = read_frames(tachyon.frame)
            geometry = calculate_geometry(frames, thr=150)
            tachyon = append_data(tachyon, geometry)
            tracks = find_tracks(tachyon, meas='width')
            print 'Tracks:', len(tracks), tracks

            plot.plot_geometry(find_data_tracks(tachyon, tracks, offset=0.1))

        tframes = read_frames(find_data_tracks(tachyon, tracks, offset=0).frame)
        plot.plot_frames(tframes)

    if 'camera' in data.keys():
        camera = data['camera']
        print 'Camera length:', len(camera)

        cframes = read_frames(find_data_tracks(camera, tracks, offset=0).frame)
        plot.plot_frames(cframes)
