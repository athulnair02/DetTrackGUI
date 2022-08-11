import os
import os.path as path
from datetime import datetime
import re
from typing import Dict
import PySimpleGUI as sg
import subprocess

DETECTION_TEMPLATE = '/nfs/scratch/athul/DetTrackGUI/DetectionNTracking_template.m'
DETECTION_RESULT = 'DetectionNTracking_result.m'
CALIBRATION_DIRNAME = 'LLSCalibration'

# TODO get rid of Cam_ and change folder check for channels, add 514 channel
CHNAME_DICT = {
    '488' : 'ch488nmCamA',
    '560' : 'ch560nmCamB',
    '642' : 'ch642nmCamA'
}

# TODO add more keys with new channel 514
CHANNEL_KEYS = ['-CH-PRIMARY-NONE-', '-CH-PRIMARY-488-', '-CH-PRIMARY-560-', '-CH-PRIMARY-642-',
'-CH-SECONDARY-NONE-', '-CH-SECONDARY-488-', '-CH-SECONDARY-560-', '-CH-SECONDARY-642-',
'-CH-SECONDARY2-NONE-', '-CH-SECONDARY2-488-', '-CH-SECONDARY2-560-', '-CH-SECONDARY2-642-'
]

MKDIR = False
RUN = False

# TODO get calib path from experiment, cs, and parent_dir
def get_calibration_path(dir_path):
    basename = path.basename(dir_path)
    if basename.startswith('Ex'):
        calibration_path = path.join(path.dirname(path.dirname(dir_path)), CALIBRATION_DIRNAME)
    elif basename.startswith('CS'):
        calibration_path = path.join(path.dirname(dir_path), CALIBRATION_DIRNAME)
    else:
        pass
    return calibration_path

def list_to_qstr(lst: list):
    lst = lst.copy()
    for i in range(len(lst)):
        lst[i] = '\'' + lst[i] + '\''
    
    return ", ".join(lst)

def check_dir(path: str, option: str):
    basename = os.path.basename(path)
    return (basename.startswith('CS') and option == 'Cover Slip') or (basename.startswith('Ex') and option == 'Experiment')

# TODO add parallel cluster profile and etc
def fill_dnt_template(condDir: str, chNames_lst: list, markers_lst: list, data_filepath: str, calibration_path: str, zspace: float, sigma_values: str, overwrite_values: str, tracking_radius_values: str, backup_dir: str, calc_img_proj: bool, bleach: bool):
    condDir = '\'' + condDir + '\''
    chNames = list_to_qstr(chNames_lst)
    markers = list_to_qstr(markers_lst)

    if RUN:
        result_path = path.join(backup_dir, DETECTION_RESULT)
    else:
        result_path = DETECTION_RESULT

    if RUN and not path.exists(backup_dir):
        return (False, 'Error: backup folder not found in primary channel\'s analysis directory. Please ensure directories follow procedural organization and naming practices')

    # Read in the file
    with open(DETECTION_TEMPLATE, 'r') as file:
        filedata = file.read()

    # Replace the target string
        filedata = filedata.replace('%condDir%', condDir)
        filedata = filedata.replace('%chNames%', chNames)
        filedata = filedata.replace('%markers%', markers)
        filedata = filedata.replace('%data_filepath%', data_filepath)
        filedata = filedata.replace('%calibration_path%', calibration_path)
        filedata = filedata.replace('%zspace%', zspace)
        filedata = filedata.replace('%sigma_values%', sigma_values)
        filedata = filedata.replace('%overwrite_values%', overwrite_values)
        filedata = filedata.replace('%tracking_radius_values%', tracking_radius_values)

        if calc_img_proj:
            filedata = filedata.replace('%calc_img_proj_option%', '')
        else:
            filedata = filedata.replace('%calc_img_proj_option%', '%')

        if bleach:
            filedata = filedata.replace('%bleach_option%', '')
        else:
            filedata = filedata.replace('%bleach_option%', '%')

        # if cme_viewer:
        #     filedata = filedata.replace('%cme_viewer_option%', '')
        # else:
        #     filedata = filedata.replace('%cme_viewer_option%', '%')

        # if labview:
        #     filedata = filedata.replace('%labview_conversion_option%', '')
        # else:
        #     filedata = filedata.replace('%labview_conversion_option%', '%')

    # Write the file out again
    with open(result_path, 'w+') as file:
        file.write(filedata)
    
    return (True, result_path)

def get_zspace(experiment_path: str):
    experiment = path.basename(experiment_path)
    zspace_str = experiment.split('_')[-1][1:].replace('p', '.')
    
    try:
        zspace = float(zspace_str)
    except:
        return (False, 'Error: zpsace name on folder cannot be parsed for float. Ensure it looks like "_z0p5"')

    return (True, zspace_str)

def get_sigmas(window, values: Dict, channels: list):
    sigmas = []
    for channel in channels:
        col_key = '-CS' + channel + 'COL-'
        cs_key = '-CS' + channel + '-' 
        sigmaXY_key = '-CS' + channel + 'XY-'
        sigmaZ_key = '-CS' + channel + 'Z-'
        if window[col_key].visible and values[cs_key]:
            sigmaXY = values[sigmaXY_key]
            sigmaZ = values[sigmaZ_key]
            try:
                float(sigmaXY)
                float(sigmaZ)
            except Exception as e:
                return (False, 'Error: Please enter both fields and only use floats for custom sigma values.')
            sigmas.append(sigmaXY + ', ' + sigmaZ)
        else:
            sigmas.append('sigmaXY' + channel + ', sigmaZ' + channel + 'corr')


    return (True, '; '.join(sigmas)) 

def get_overwrites(values: Dict):
    deskew = "false, "
    
    if values['-DETECTION-']:
        detection = 'true, '
    else:
        detection = 'false, '
    
    if values['-TRACKING-TRACKPROCESS-']:
        tracking = 'true, true'
    else:
        tracking = 'false, false'

    return deskew + detection + tracking

def check_one_or_none(a: bool, b: bool, c: bool):
    return a + b + c <= 1

# TODO better way to do this?
def get_channels(values: Dict):
    primary_none = values['-CH-PRIMARY-NONE-']
    secondary_none = values['-CH-SECONDARY-NONE-']
    secondary2_none = values['-CH-SECONDARY2-NONE-']

    if primary_none:
        return (False, 'Error: Ensure primary channel is not "None".', None)

    if (not primary_none and values['-PRIMARY-MARKER-'] == '') or (not secondary_none and values['-SECONDARY-MARKER-'] == '') or (not secondary2_none and values['-SECONDARY2-MARKER-'] == ''):
        return (False, 'Error: Ensure marker is entered for selected channels.', None)

    primary_488 = values['-CH-PRIMARY-488-']
    secondary_488 = values['-CH-SECONDARY-488-']
    secondary2_488 = values['-CH-SECONDARY2-488-']

    if not check_one_or_none(primary_488, secondary_488, secondary2_488):
        return (False, 'Error: Ensure a wavelength is selected only for one channel.', None)

    primary_560 = values['-CH-PRIMARY-560-']
    secondary_560 = values['-CH-SECONDARY-560-']
    secondary2_560 = values['-CH-SECONDARY2-560-']

    if not check_one_or_none(primary_560, secondary_560, secondary2_560):
        return (False, 'Error: Ensure a wavelength is selected only for one channel.', None)

    primary_642 = values['-CH-PRIMARY-642-']
    secondary_642 = values['-CH-SECONDARY-642-']
    secondary2_642 = values['-CH-SECONDARY2-642-']

    if not check_one_or_none(primary_642, secondary_642, secondary2_642):
        return (False, 'Error: Ensure a wavelength is selected only for one channel.', None)
    
    channels = []
    markers = []
    # Primary channel
    if primary_488:
        channels.append('488')
    elif primary_560:
        channels.append('560')
    elif primary_642:
        channels.append('642')
    markers.append(values['-PRIMARY-MARKER-'])
    # Secondary channel
    if secondary_488:
        channels.append('488')
    elif secondary_560:
        channels.append('560')
    elif secondary_642:
        channels.append('642')

    if not secondary_none:
        markers.append(values['-SECONDARY-MARKER-'])

    # Secondary2 channel
    if secondary2_488:
        channels.append('488')
    elif secondary2_560:
        channels.append('560')
    elif secondary2_642:
        channels.append('642')
    
    if not secondary2_none:
        markers.append(values['-SECONDARY2-MARKER-'])

    return (True, channels, markers)

def build_dict(experiment_path):
    channel_dirs = list(filter(lambda x: x.startswith('ch'), os.listdir()))

    for channel_dir in channel_dirs:
        num = re.findall(r'\d+', channel_dir)
        CHNAME_DICT[num] = channel_dir

def check_channel_paths(chNames: list, experiment_path: str):
    for chName in chNames:
        channel_path = path.join(experiment_path, chName)
        if not path.exists(channel_path):
            return False

    return True

def get_tracking_radius(values: Dict):
    try:
        lower_bound = values['-TRACKING-RADIUS-LOWER-']
        upper_bound = values['-TRACKING-RADIUS-UPPER-']
        
        if bool(lower_bound == '') ^ bool(upper_bound == ''):
            return (False, 'Error: Please enter both lower and upper bounds if not using the default tracking radius')
        elif lower_bound == '' and upper_bound == '':
            lower_bound = '3'
            upper_bound = '6'
        elif int(lower_bound) >= int(upper_bound):
            return (False, 'Error: Please ensure the lower bound is less than the upper bound for the tracking radius')

    except Exception as e:
        return (False, 'Error: Please enter only numbers for the tracking radius')
    else:
        return (True, lower_bound + ' ' + upper_bound)

def get_apath(experiment_path: str, primary_chName: str, mkdir: bool=True):
    apath = path.join(experiment_path, primary_chName, 'Analysis', '')
    if not path.exists(apath) and mkdir:
        os.mkdir(apath)
        print('mkdir')

    return apath

def get_backup_dir(apath: str, backup_dirname: str, mkdir: bool=True):
    if backup_dirname == None:
        backup_dirname = path.join(apath, datetime.now().strftime('backup_%m_%d_%Y_%H_%M'))
    else:
        backup_dirname = path.join(apath, backup_dirname)
    if not path.exists(backup_dirname) and mkdir:
        os.mkdir(backup_dirname)
        print('mkdir')
    return backup_dirname

def get_data_filename(channels: list):
    return 'data_' + '_'.join(channels)

def any_selected(d, lst):
    return bool(sum([d[a] for a in lst]))
    
def show_sigmas(window, values: Dict, event: str):
    bool_488 = any_selected(values, CHANNEL_KEYS[1::4])
    bool_560 = any_selected(values, CHANNEL_KEYS[2::4])
    bool_642 = any_selected(values, CHANNEL_KEYS[3::4])
    
    window['-CS488COL-'].update(visible=bool_488)
    window['-CS560COL-'].update(visible=bool_560)
    window['-CS642COL-'].update(visible=bool_642)

    window['-CS488XYT-'].update(visible=values['-CS488-'])
    window['-CS488XY-'].update(visible=values['-CS488-'])
    window['-CS488ZT-'].update(visible=values['-CS488-'])
    window['-CS488Z-'].update(visible=values['-CS488-'])

    window['-CS560XYT-'].update(visible=values['-CS560-'])
    window['-CS560XY-'].update(visible=values['-CS560-'])
    window['-CS560ZT-'].update(visible=values['-CS560-'])
    window['-CS560Z-'].update(visible=values['-CS560-'])
    
    window['-CS642XYT-'].update(visible=values['-CS642-'])
    window['-CS642XY-'].update(visible=values['-CS642-'])
    window['-CS642ZT-'].update(visible=values['-CS642-'])
    window['-CS642Z-'].update(visible=values['-CS642-'])

def run_cmd(det_track_path: str):
    matlab_cmd = f'matlab -nodisplay -nosplash -nodesktop -r "run(\'{det_track_path}\');exit;" | tail -n +13'
    print(matlab_cmd)
    p1 = subprocess.run(matlab_cmd, capture_output=True, text=True, shell=True, input='exit;')
    print('stdout: ' + p1.stdout)
    print('stderr: ' + p1.stderr)
    print('returncode: ' + str(p1.returncode))

    return (p1.stderr == '', p1.stderr)

# TODO deal with possible errors, add files after bleach_in_a_box
def move_files_to_backup(apath: str, backup_dir):
    files = [path.join(apath, 'Detection3D.mat'), path.join(apath, 'ProcessedTracks.mat'), path.join(apath, 'RotatedTracks.mat'), path.join(apath, 'trackedFeatures.mat')]
    
    for file in files:
        p = subprocess.run(f'cp {file} {backup_dir}', capture_output=True, text=True, shell=True)
        print(f'stderr {file}: ' + p.stderr)

def run_experiment(window, values: Dict, experiment_path: str, backup_dirname: str=None):
    calibration_path = get_calibration_path(experiment_path)
    print(calibration_path)
    if not path.isdir(calibration_path):
        return (False, f'Error: Calibration folder not found. Ensure it is named \"{CALIBRATION_DIRNAME}\" and is in the same directory as the Cover Slip directories.')
    
    ch_success, channels, markers = get_channels(values)
    if not ch_success:
        return (ch_success, channels)

    build_dict(channels)
    print(CHNAME_DICT)

    chNames = list(map(lambda x: CHNAME_DICT[x], channels))
    print(chNames)

    if not check_channel_paths(chNames, experiment_path):
        return (False, f'Error: Channel data directory not found in experiment directory {experiment_path}. Please ensure it is there.')

    print(*markers)

    zspace_success, zspace = get_zspace(experiment_path)
    if not zspace_success:
        return (zspace_success, zspace)
    print(zspace)

    sigma_sucess, sigma_values = get_sigmas(window, values, channels)
    if not sigma_sucess:
        return (sigma_sucess, sigma_values)

    print(sigma_values)

    overwrite_values = get_overwrites(values)
    print(overwrite_values)

    tracking_radius_success, tracking_radius_values = get_tracking_radius(values)
    if not tracking_radius_success:
        return (tracking_radius_success, tracking_radius_values)
    print(tracking_radius_values)

    apath = get_apath(experiment_path, chNames[0], mkdir=MKDIR)
    print(apath)
  
    backup_dir = get_backup_dir(apath, backup_dirname, mkdir=MKDIR)
    print(backup_dir)

    data_filename = get_data_filename(channels)
    print(data_filename)

    data_filepath = path.join(backup_dir, data_filename)

    calc_img_proj = values['-CALCIMGPROJ-']
    bleach = values['-BLEACH-']
    # cme_viewer = values['-CME_VIEWER-']
    # labview = values['-LABVIEW-']

    fill_succes, result_path = fill_dnt_template(experiment_path, chNames, markers, data_filepath, calibration_path, zspace, sigma_values, overwrite_values, tracking_radius_values, backup_dir, calc_img_proj, bleach)
    
    if not fill_succes:
        return (fill_succes, result_path)

    if RUN:
        run_success, run_error =  run_cmd(result_path)

        if not run_success:
            return (run_success, f'Error: run failed.\n {run_error}')

        print('Run worked :)')

        move_files_to_backup(apath, backup_dir)

    return (True, None)

def run_cover_slip(window, values: Dict, cs_path: str):
    # Run each experiment in the cover slip dir
    experiment_lst = list(filter(lambda x: x.startswith('Ex'), os.listdir(cs_path)))
    if not experiment_lst:
        return (False, 'Error: No experiments found in cover slip directory. Please ensure experiments begin with "Ex"')
    print(experiment_lst)

    backup_dirname = datetime.now().strftime('backup_%m_%d_%Y_%H_%M')
    print(backup_dirname)

    for experiment in experiment_lst:
        experiment_path = path.join(cs_path, experiment)
        print(f'Running on {experiment_path}')
        success, message = run_experiment(window, values, experiment_path, backup_dirname)
        if not success:
            return (success, experiment + ' ' + message)

    return (True, None)
    

def main():        
    option_chosen = 'Cover Slip'
    sg.theme('Tan')

    custom_sigma_488_col = [
        [sg.Checkbox('Custom 488nm Sigmas', enable_events=True, key='-CS488-')],
        [sg.Text('XY:', key='-CS488XYT-'), sg.In(size=(4,1), key='-CS488XY-')],
        [sg.Text('Z: ', key='-CS488ZT-'), sg.In(size=(4,1), key='-CS488Z-')]
    ]

    custom_sigma_560_col = [
        [sg.Checkbox('Custom 560nm Sigmas', enable_events=True, key='-CS560-')],
        [sg.Text('XY:', key='-CS560XYT-'), sg.In(size=(4,1), key='-CS560XY-')],
        [sg.Text('Z: ', key='-CS560ZT-'), sg.In(size=(4,1), key='-CS560Z-')]
    ]

    custom_sigma_642_col = [
        [sg.Checkbox('Custom 642nm Sigmas', enable_events=True, key='-CS642-')],
        [sg.Text('XY:', key='-CS642XYT-'), sg.In(size=(4,1), key='-CS642XY-')],
        [sg.Text('Z: ', key='-CS642ZT-'), sg.In(size=(4,1), key='-CS642Z-')]
    ]

    empty_col = [
        [sg.Text(' ')],
        [sg.Text(' ')],
        [sg.Text(' ')]
    ]

    layout = [
        # Selecting what to run detection on
        [
            sg.Text('Run detection on*:', size=(17, 1)),
            sg.Radio('Cover Slip', 'detection-option', default=True, enable_events=True, key="-DETECT-ON-"),
            sg.Radio('Single Experiment', 'detection-option', default=False, enable_events=True, key="-DETECT-ON2-")
        ],
        # Select directory
        [
            sg.Text(f'Select the {option_chosen} directory*:', key='-SELECT-MESSAGE-'), 
            sg.In(size=(50,1), enable_events=True, key='-FOLDER-'), 
            sg.FolderBrowse()
        ],
        # Primary channel
        [
            sg.Text('Select primary channel*:', size=(30, 1)),
            sg.Radio('None', 'primary-ch', default=True, enable_events=True, key=CHANNEL_KEYS[0]),
            sg.Radio('488nm', 'primary-ch', default=False, enable_events=True, key=CHANNEL_KEYS[1]),
            sg.Radio('560nm', 'primary-ch', default=False, enable_events=True, key=CHANNEL_KEYS[2]),
            sg.Radio('642nm', 'primary-ch', default=False, enable_events=True, key=CHANNEL_KEYS[3]),
            sg.Text('Enter a marker:'),
            sg.In(size=(5,1), key='-PRIMARY-MARKER-')
        ],
        # Secondary channel
        [
            sg.Text('Select secondary channel:', size=(30, 1)),
            sg.Radio('None', 'secondary-ch', default=True, enable_events=True, key=CHANNEL_KEYS[4]),
            sg.Radio('488nm', 'secondary-ch', default=False, enable_events=True, key=CHANNEL_KEYS[5]),
            sg.Radio('560nm', 'secondary-ch', default=False, enable_events=True, key=CHANNEL_KEYS[6]),
            sg.Radio('642nm', 'secondary-ch', default=False, enable_events=True, key=CHANNEL_KEYS[7]),
            sg.Text('Enter a marker:'),
            sg.In(size=(5,1), key='-SECONDARY-MARKER-')
        ],
        # Secondary2 channel
        [
            sg.Text('Select another secondary channel:', size=(30, 1)),
            sg.Radio('None', 'secondary2-ch', default=True, enable_events=True, key=CHANNEL_KEYS[8]),
            sg.Radio('488nm', 'secondary2-ch', default=False, enable_events=True, key=CHANNEL_KEYS[9]),
            sg.Radio('560nm', 'secondary2-ch', default=False, enable_events=True, key=CHANNEL_KEYS[10]),
            sg.Radio('642nm', 'secondary2-ch', default=False, enable_events=True, key=CHANNEL_KEYS[11]),
            sg.Text('Enter a marker:'),
            sg.In(size=(5,1), key='-SECONDARY2-MARKER-')
        ],
        # Tracking radius
        [
            sg.Text('Tracking Radius (Default [3 6]):'),
            sg.Text('Lower Bound:'),
            sg.In(size=(4,1), key='-TRACKING-RADIUS-LOWER-'),
            sg.Text('Upper Bound:'),
            sg.In(size=(4,1), key='-TRACKING-RADIUS-UPPER-')
        ],
        # Overwrites
        [
            sg.Text('Overwrite:'),
            sg.Checkbox('Detection', key='-DETECTION-'),
            sg.Checkbox('Tracking & Track Processing', key='-TRACKING-TRACKPROCESS-'),
        ],
        # Custom Sigma Values
        [
            sg.Column(empty_col, visible=True, key='-EMPTY-COL-'),
            sg.Column(custom_sigma_488_col, element_justification='c', visible=False, key='-CS488COL-'),
            sg.Column(custom_sigma_560_col, element_justification='c', visible=False, key='-CS560COL-'),
            sg.Column(custom_sigma_642_col, element_justification='c', visible=False, key='-CS642COL-')
        ],
        # Select run options
        [
            sg.Checkbox('Run GU_calcImageProjections', key='-CALCIMGPROJ-'),
            sg.Checkbox('Run bleach_in_a_box', key='-BLEACH-'),
            # sg.Checkbox('Run GU_cme3d2dViewer', key='-CME_VIEWER-'),
            # sg.Checkbox('Open MicroscopyBrowser_v4', key='-LABVIEW-')
        ],
        # Run button
        [
            sg.Button('Run', key='-RUN-')
        ],
        # Legend
        [
            sg.Text('* = Required')
        ]
    ]

    window = sg.Window(title='Detection and Tracking', layout=layout, margins=(100,50)) 
    while True:
        event, values = window.read()
        
        if event == sg.WIN_CLOSED or event=="Exit" or event == None:
            break

        elif event == '-DETECT-ON-' or event == '-DETECT-ON2-': 
            if values['-DETECT-ON-'] == True:
                option_chosen = 'Cover Slip'
            else:
                option_chosen = 'Experiment'
            window['-SELECT-MESSAGE-'].update(f'Select the {option_chosen} folder:')

        elif event == '-FOLDER-':
            if not check_dir(values['-FOLDER-'], option_chosen):
                sg.Popup('Folder chosen does not match option selected. Please change the option or folder')
                window['-FOLDER-'].update('')
            else:
                pass # TODO grab channels from PSF

        elif event.startswith('-CH-') or 'CS' in event:
            window['-EMPTY-COL-'].update(visible=False)
            show_sigmas(window, values, event)

        elif event == '-RUN-':
            print('RUNNING')
            if option_chosen == 'Cover Slip':
                success, message = run_cover_slip(window, values, values['-FOLDER-'])
                if not success:
                    sg.Popup(message)

            elif option_chosen == 'Experiment':
                success, message = run_experiment(window, values, values['-FOLDER-'])
                if not success:
                    sg.Popup(message)


        
    window.close()

main()

