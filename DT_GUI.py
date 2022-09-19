import os
import os.path as path
from datetime import datetime
import re
from typing import Dict
import PySimpleGUI as sg
import subprocess
import smtplib
from email.message import EmailMessage


class GUIError(Exception):
    """Exception raised for errors in the GUI unrelated to subprocess errors.
       Made for the purpose of not sending an email regarding simple GUI

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

DETECTION_TEMPLATE = '/nfs/scratch/athul/DetTrackGUI/DetectionNTracking_template.m'
DETECTION_RESULT = 'DetectionNTracking_result.m'
CALIBRATION_DIRNAME = 'LLSCalibrations'

SUCCESS_EMAIL = 'Hello! \n\nYour Detection & Tracking has finished running! Please check the GUI and your results.\n\nBest,\nMr. GUI'
FAILURE_EMAIL = 'Uh Oh! \n\nYour Detection & Tracking has come across an ERROR! Please check the GUI and your results.\n\nBest,\nMr. GUI'

CHANNELS = []

CHNAME_DICT = {}

MKDIR = False
RUN = MKDIR

# TODO get calib path from parent_dir
def get_calibration_path(dir_path):
    basename = path.basename(dir_path)
    calibration_path = ''
    if basename.startswith('Ex'):
        calibration_path = path.join(path.dirname(path.dirname(dir_path)), CALIBRATION_DIRNAME)
    elif basename.startswith('CS'):
        calibration_path = path.join(path.dirname(dir_path), CALIBRATION_DIRNAME)
    else:
        pass
    
    if not path.isdir(calibration_path):
        raise GUIError(f'Error: Calibration folder not found. Ensure it is named \"{CALIBRATION_DIRNAME}\" and is in the same directory as the Cover Slip directories.')

    return calibration_path

def list_to_qstr(lst: list):
    lst = lst.copy()
    for i in range(len(lst)):
        lst[i] = '\'' + lst[i] + '\''
    
    return ", ".join(lst)

def check_dir(path: str, option: str):
    basename = os.path.basename(path)
    return (basename.startswith('CS') and option == 'Cover Slip') or (basename.startswith('Ex') and option == 'Experiment')

def fill_dnt_template(condDir: str, chNames_lst: list, markers_lst: list, data_filepath: str, calibration_path: str, zspace: float, sigma_values: str, overwrite_values: str, tracking_radius_values: str, backup_dir: str, calc_img_proj: bool, bleach: bool):
    condDir = '\'' + condDir + '\''
    chNames = list_to_qstr(chNames_lst)
    markers = list_to_qstr(markers_lst)

    if RUN:
        result_path = path.join(backup_dir, DETECTION_RESULT)
    else:
        result_path = DETECTION_RESULT

    if RUN and not path.exists(backup_dir):
        raise GUIError('Error: backup folder not found in primary channel\'s analysis directory. Please ensure directories follow procedural organization and naming practices')

    # PSFs, Default Sigmas Fill
    psfs = ''
    default_sigmas_calc = ''
    default_sigmas = ''
    for channel in CHANNELS:
        psfs += f'PSF{channel} = \'{channel}totalPSF.tif\';\n'
        default_sigmas_calc += f'[sigmaXY{channel}, sigmaZ{channel}] = GU_estimateSigma3D([PSFrt filesep],PSF{channel});\n'
        default_sigmas += f'sigmaZ{channel}corr = sigmaZ{channel}/zRatio;\n'

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
        filedata = filedata.replace('%psfs%', psfs)
        filedata = filedata.replace('%default_sigmas_calc%', default_sigmas_calc)
        filedata = filedata.replace('%default_sigmas%', default_sigmas)
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

    # Write the file out again
    with open(result_path, 'w+') as file:
        file.write(filedata)
    
    return result_path

def get_zspace(experiment_path: str):
    experiment = path.basename(experiment_path)
    zspace_str = experiment.split('_')[-1][1:].replace('p', '.')
    
    try:
        zspace = float(zspace_str)
    except:
        raise('Error: zpsace name on folder cannot be parsed for float. Ensure it looks like "_z0p5"')

    return zspace_str

def get_sigmas(window, values: Dict, channels_index: list):
    sigmas = [] # TODO check this
    for i in channels_index:
        i_str = str(i)
        col_key = '-CS' + i_str + 'COL-'
        cs_key = '-CS' + i_str + '-' 
        sigmaXY_key = '-CS' + i_str + 'XY-'
        sigmaZ_key = '-CS' + i_str + 'Z-'
        if window[col_key].visible and values[cs_key]:
            sigmaXY = values[sigmaXY_key]
            sigmaZ = values[sigmaZ_key]
            try:
                float(sigmaXY)
                float(sigmaZ)
            except:
                raise GUIError('Error: Please enter both fields and only use floats for custom sigma values.')
            sigmas.append(f'{sigmaXY}, {sigmaZ}')
        else:
            channel = values[f'-CH-{i}-']
            sigmas.append(f'sigmaXY{channel}, sigmaZ{channel}corr')


    return '; '.join(sigmas) 

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

def get_channels(values: Dict):
    # check if primary channel is filled
    if values['-CH-1-'] == '':
        raise GUIError('Error: Ensure primary channel is not empty.')

    # check if selected channels have markers filled
    channels = []
    channels_index = []
    markers = []
    for i in range(1, 4):
        channel = values[f'-CH-{i}-']
        marker = values[f'-MARKER-{i}-']
        if channel != '':
            if marker == '':
                raise GUIError('Error: Ensure marker is entered for selected channels.')
            channels.append(channel)
            channels_index.append(i)
            markers.append(marker)

    # check channels selected only once
    if len(channels) != len(set(channels)):
        raise GUIError('Error: Ensure a wavelength is selected only for one channel.')

    return (channels, markers, channels_index)

def load_channels(calibration_path):
    channels = filter(lambda x: x.endswith('totalPSF.tif'), os.listdir(calibration_path))
    channels = list(map(lambda x: re.findall(r'\d+', x)[0], channels))
    channels.sort()
    if not channels:
        raise GUIError('Error: No channels found in calibration folder')

    global CHANNELS
    CHANNELS = channels

    return channels

# TODO: update for exisitng channels
def build_dict(experiment_path):
    global CHNAME_DICT
    channel_dirs = list(filter(lambda x: x.startswith('ch'), os.listdir(experiment_path)))

    for channel_dir in channel_dirs:
        num = re.findall(r'\d+', channel_dir)[0]
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
            raise GUIError('Error: Please enter both lower and upper bounds if not using the default tracking radius')
        elif lower_bound == '' and upper_bound == '':
            lower_bound = '3'
            upper_bound = '6'
        elif int(lower_bound) >= int(upper_bound):
            raise GUIError('Error: Please ensure the lower bound is less than the upper bound for the tracking radius')

    except Exception as e:
        raise GUIError('Error: Please enter only numbers for the tracking radius')
    else:
        return lower_bound + ' ' + upper_bound

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

def control_channel_selection(window, values: Dict, event: str):
    channel_selected = values[event]
    selected_lst = [False, False, False]
    for i in range (1, 4):
        key = f'-CH-{i}-'
        if values[key] != '':
            selected_lst[i - 1] = True
        if event != key and values[key] == channel_selected:
            window[key].update('')
            window[f'-MARKER-{i}-'].update('')
            selected_lst[i - 1] = False
        
    return selected_lst

def update_channel_dropdowns(window):
    dropdown_list = [''] + CHANNELS
    for i in range(1, 4):
        window[f'-CH-{i}-'].update(values=dropdown_list)
        window[f'-MARKER-{i}-'].update('')

def show_sigmas(window, values: Dict, selected_lst: list, event: str):
    for i in range(1, 4):
        selected = selected_lst[i - 1]
        window[f'-CS{i}COL-'].update(visible=selected)
        window[f'-CS{i}XYT-'].update(visible=values[f'-CS{i}-'])
        window[f'-CS{i}XY-'].update(visible=values[f'-CS{i}-'])
        window[f'-CS{i}ZT-'].update(visible=values[f'-CS{i}-'])
        window[f'-CS{i}Z-'].update(visible=values[f'-CS{i}-'])

def run_cmd(det_track_path: str):
    matlab_cmd = f'matlab -nodisplay -nosplash -nodesktop -r "run(\'{det_track_path}\');exit;" | tail -n +13'
    print(matlab_cmd)
    p1 = subprocess.run(matlab_cmd, capture_output=True, text=True, shell=True, input='exit;')
    print('stdout: ' + p1.stdout)
    print('stderr: ' + p1.stderr)
    print('returncode: ' + str(p1.returncode))

    if p1.stderr != '':
        raise Exception(f'Error: run failed.\n {p1.stderr}')


# TODO deal with possible errors, add files after bleach_in_a_box
def move_files_to_backup(apath: str, backup_dir: str, bleach: bool):
    files = ['Detection3D.mat', 'ProcessedTracks.mat', 'RotatedTracks.mat', 'trackedFeatures.mat']
    
    if bleach:
        files.append('orig_ProcessedTracks.mat')

    files = list(map(lambda x: path.join(apath, x), files))

    for file in files:
        p = subprocess.run(f'cp {file} {backup_dir}', capture_output=True, text=True, shell=True)
        print(f'stderr {file}: ' + p.stderr)

def run_experiment(window, values: Dict, experiment_path: str, backup_dirname: str=None):
    calibration_path = get_calibration_path(experiment_path)
    print('Calibration dir:', calibration_path)
    
    channels, markers, channels_index = get_channels(values)

    build_dict(experiment_path)
    print('Channel name dictionary:', CHNAME_DICT)

    chNames = list(map(lambda x: CHNAME_DICT[x], channels))
    print('Channel names:', chNames)

    if not check_channel_paths(chNames, experiment_path):
        raise GUIError('Error: Channel data directory not found in experiment directory {experiment_path}. Please ensure it is there.')

    print('Markers:', markers)

    zspace = get_zspace(experiment_path)
    print('Zspace:', zspace)

    sigma_values = get_sigmas(window, values, channels_index)
    print('Sigma Values:', sigma_values)

    overwrite_values = get_overwrites(values)
    print('Overwrite Values:', overwrite_values)

    tracking_radius_values = get_tracking_radius(values)
    print('Tracking Radius Values:', tracking_radius_values)

    apath = get_apath(experiment_path, chNames[0], mkdir=MKDIR)
    print('Analysis Path:', apath)
  
    backup_dir = get_backup_dir(apath, backup_dirname, mkdir=MKDIR)
    print('Backup Dir:', backup_dir)

    data_filename = get_data_filename(channels)
    print('Data Filename:', data_filename)

    data_filepath = path.join(backup_dir, data_filename)

    calc_img_proj = values['-CALCIMGPROJ-']
    bleach = values['-BLEACH-']

    result_path = fill_dnt_template(experiment_path, chNames, markers, data_filepath, calibration_path, zspace, sigma_values, overwrite_values, tracking_radius_values, backup_dir, calc_img_proj, bleach)

    if RUN:
        run_cmd(result_path)
        print('Run worked :)')

        move_files_to_backup(apath, backup_dir, bleach)

def run_cover_slip(window, values: Dict, cs_path: str):
    # Run each experiment in the cover slip dir
    experiment_lst = list(filter(lambda x: x.startswith('Ex'), os.listdir(cs_path)))
    if not experiment_lst:
        raise GUIError('Error: No experiments found in cover slip directory. Please ensure experiments begin with "Ex"')
    print('Experiment list:', experiment_lst)

    backup_dirname = datetime.now().strftime('backup_%m_%d_%Y_%H_%M')
    print('Backupdir name:', backup_dirname)

    for experiment in experiment_lst:
        experiment_path = path.join(cs_path, experiment)
        print(f'Running on {experiment_path}')

        try:
            run_experiment(window, values, experiment_path, backup_dirname)
        except GUIError as e:
            raise GUIError(e)
        except Exception as e:
            raise Exception(experiment + ' ' + e)

    
def send_email(recepient: str, success_msg: str):
    if recepient == '':
        sg.Popup('No email')
        return

    try:
        msg = EmailMessage()
        msg.set_content(success_msg)
        msg['Subject'] = 'Detection & Tracking Update'
        msg['From'] = 'tklab@tklab.hms.harvard.edu'
        msg['To'] = recepient

        server = smtplib.SMTP('smtp.gmail.com', 587)

        server.starttls()
        server.login('tklab@tklab.hms.harvard.edu', 'Clathrin2020g')
        server.send_message(msg)
        server.quit()
        print('Email Sent')
        sg.Popup('Email Sent!')
    except:
        sg.Popup('Bad email entered, please try again!')


def main():        
    option_chosen = 'Cover Slip'
    sg.theme('Tan')

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
            sg.Text('Select channel #1 (primary)*:', size=(30, 1))
        ],
        # Secondary channel
        [
            sg.Text('Select channel #2 (secondary):', size=(30, 1))
        ],
        # Secondary2 channel
        [
            sg.Text('Select channel #3 (secondary):', size=(30, 1))
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
            sg.Checkbox('Tracking & Track Processing', key='-TRACKING-TRACKPROCESS-')
        ],
        # Custom Sigma Values
        [
            sg.Column(empty_col, visible=True, key='-EMPTY-COL-')
            
        ],
        # Select run options
        [
            sg.Checkbox('Run GU_calcImageProjections', key='-CALCIMGPROJ-'),
            sg.Checkbox('Run bleach_in_a_box', key='-BLEACH-'),
        ],
        # Email
        [
            sg.Text('Enter your email to be notified of completion:'),
            sg.Input(size=(30, 1), key='-EMAIL-')
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

    # Adding channel and marker components to layout
    for i in range(2, 5):
        elem = layout[i]
        elem.append(sg.Combo(values=CHANNELS, readonly=True, enable_events=True, size=(4, 1) ,key=f'-CH-{i - 1}-'))
        elem.append(sg.Text('Enter a marker:'))
        elem.append(sg.In(size=(5,1), key=f'-MARKER-{i - 1}-'))

    # Adding custom sigma components to layout
    custom_sigmas_cols = layout[7]

    for i in range(1, 4):
        cs_str = f'Channel #{i} Custom Sigmas'
        custom_sigma_col = [
            [sg.Checkbox(cs_str, enable_events=True, key=f'-CS{i}-')],
            [sg.Text('XY:', key=f'-CS{i}XYT-'), sg.In(size=(4,1), key=f'-CS{i}XY-')],
            [sg.Text('Z: ', key=f'-CS{i}ZT-'), sg.In(size=(4,1), key=f'-CS{i}Z-')]
        ]
        custom_sigmas_cols.append(sg.Column(custom_sigma_col, element_justification='c', visible=False, key=f'-CS{i}COL-'))

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
                try:
                    calibration_path = get_calibration_path(values['-FOLDER-'])
                    channels = load_channels(calibration_path) 
                except Exception as e:
                    sg.Popup(e) 
                else:
                    update_channel_dropdowns(window)
                    print('Detected Channels:', channels)           

        elif event.startswith('-CH-') or 'CS' in event:
            window['-EMPTY-COL-'].update(visible=False)
            selected_lst = control_channel_selection(window, values, event)
    
            show_sigmas(window, values, selected_lst, event)

        elif event == '-RUN-':
            print('RUNNING')
            if option_chosen == 'Cover Slip':
                try:
                    run_cover_slip(window, values, values['-FOLDER-'])
                except GUIError as e:
                    sg.Popup(e)
                except Exception as e:
                    sg.Popup(e)

            elif option_chosen == 'Experiment':
                try:
                    run_experiment(window, values, values['-FOLDER-'])
                except GUIError as e:
                    sg.Popup(e)
                except Exception as e:
                    sg.Popup(e)
                    send_email(values['-EMAIL-'], FAILURE_EMAIL)
                else:
                    send_email(values['-EMAIL-'], SUCCESS_EMAIL)

    window.close()

main()
