import multiprocessing
import time
import argparse
from mqtt_msg import mqtt_worker
from web_capture import capture_webpage
import sys
import os
import json

def parse_opt(known=False):
    parser = argparse.ArgumentParser()
    # mqtt broker config
    parser.add_argument('--mqtt_broker', type=str, default="192.168.3.37", help='mqtt boker server ip')
    parser.add_argument('--mqtt_port', type=int, default=1883, help='mqtt boker port')
    parser.add_argument('--mqtt_client_id', type=str, default= f"python-mqtt-sub-{int(time.time())}", help='mqtt client id')
    parser.add_argument('--mqtt_usrname', type=str, default="usrname", help='mqtt boker usrname')
    parser.add_argument('--mqtt_password', type=str, default="***", help='mqtt boker password')
    parser.add_argument('--mqtt_recv_ctrl_topic', type=str, default="/homeassiatant/sensor_86/touch_x_y",help='recv torch coordinates form mqtt')
    #if out_type == mqtt
    parser.add_argument('--mqtt_send_screen_topic', type=str, default="/homeassiatant/sensor_86/webshot",help='send webpage screenshot to mqtt')
    parser.add_argument('--mqtt_recv_queue_len', type=int, default=2, help='mqtt queue recv len')
    parser.add_argument('--mqtt_send_queue_len', type=int, default=5, help='mqtt queue send len')

    # webview config
    parser.add_argument('--viewport_width', type=int, default=480, help='config web windows width')
    parser.add_argument('--viewport_height', type=int, default=480, help='config web windows height')
    parser.add_argument('--viewport_usrname', type=str, default="usrname", help='mqtt boker usrname')
    parser.add_argument('--viewport_password', type=str, default="***", help='mqtt boker password')
    # normal config
    parser.add_argument('--touch_width', type=int, default=480, help='config web windows width')
    parser.add_argument('--touch_height', type=int, default=480, help='config web windows height')
    parser.add_argument('--url', type=str, default="http://192.168.3.37:8123/hacs-databoard/home", help='control & screenshot url addr')
    parser.add_argument('--send_hz', type=int, default=5, help='send frq (hz)')
    parser.add_argument('--out_type', type=str, default="mqtt", help='send screen(shot) to mqtt or file or multicas_udp')
    parser.add_argument('--send_buffer', type=int, default=2000,help='send image buffer')
    #if out-type == file
    parser.add_argument('--savedir', type=str, default="./",help='save screenshot dir')
    parser.add_argument('--savename', type=str, default="webpage_screenshot", help='save screenshot file name')
    #if out-type == multicas_udp
    parser.add_argument('--multicas_udp_ip', type=str, default="multicas udp",help='multicas udp ip')
    parser.add_argument('--multicas_udp_port', type=int, default=62328, help='multicas udp port')
    return parser.parse_known_args()[0] if known else parser.parse_args()

def init_opt_by_docker_env(opt,screen_num):
    if 'PYTHON_IN_DOCKER' not in os.environ:
        # 读取 .env 文件
        import dotenv
        dotenv.load_dotenv(verbose=True)
    if os.path.isfile('/data/options.json'):
        with open('/data/options.json') as f:
            options = json.load(f)
        try:
            for key, value in options.items():
                os.environ[key] = str(value)
            print(f"当前以Homeassistant Add-on 形式运行.")
        except Exception as e:
            print(f"Failing to read the options.json file, the program will exit with an error message: {e}.")
            sys.exit()
    try:
        opt.mqtt_broker = os.getenv("MQTT_BROKER")
        opt.mqtt_port = int(os.getenv("MQTT_PORT"))
        opt.mqtt_usrname = os.getenv("MQTT_USRNAME")
        opt.mqtt_password = os.getenv("MQTT_PASSWD")
        opt.viewport_width = int(os.getenv("WEB%d_VIEW_WIDTH"%screen_num))
        opt.viewport_height = int(os.getenv("WEB%d_VIEW_HEIGHT"%screen_num))
        opt.url = os.getenv("SCREEN%d_URL"%screen_num)
        opt.touch_width = int(os.getenv("SCREEN%d_WIDTH"%screen_num))
        opt.touch_height = int(os.getenv("SCREEN%d_HEIGHT"%screen_num))
        opt.viewport_usrname = os.getenv("SCREEN%d_USRNAME"%screen_num)
        opt.viewport_password = os.getenv("SCREEN%d_PASSWD"%screen_num)
        opt.mqtt_send_screen_topic = os.getenv("SCREEN%d_SEND_TOPIC"%screen_num)
        opt.mqtt_recv_ctrl_topic = os.getenv("SCREEN%d_RCV_TOPIC"%screen_num)
        opt.send_hz = int(os.getenv("SCREEN%d_DUMP_HZ"%screen_num))
        opt.send_buffer = int(os.getenv("SCREEN%d_SEND_BUFFER"%screen_num))

        print(f"The current run runs as a docker image. send buffer is:",opt.send_buffer)
    except Exception as e:
        print(f"Failing to read the .env file, the program will exit with an error message: {e}.")
        sys.exit()
def get_max_url_config():
    max_url_num=1
    if 'PYTHON_IN_DOCKER' not in os.environ:
        # 读取 .env 文件
        import dotenv
        dotenv.load_dotenv(verbose=True)
    try:
        for i in range(1,6):
            url = os.getenv("SCREEN%d_URL" % i)
            print(url)
            if url !="" and url != None:
                max_url_num = max_url_num + 1
    except:
        print(f"Failing to read the .env file, the program will exit with an error message: {e}.")
        sys.exit()
    return max_url_num

if __name__ == '__main__':
    jobs = []
    opt = parse_opt()
    #for add on docker
    max_url_num = get_max_url_config()
    #max_url_num = 1
    print("star %d url capture.."%max_url_num)
    for i in range(0,max_url_num):
        init_opt_by_docker_env(opt,i+1)
        #mqtt收发服务
        mqtt_q_recv = multiprocessing.Queue(opt.mqtt_recv_queue_len)
        mqtt_q_send = multiprocessing.Queue(opt.mqtt_send_queue_len)
        args = [opt,mqtt_q_recv,mqtt_q_send]
        p = multiprocessing.Process(target=mqtt_worker, args=(args,))
        jobs.append(p)
        p.start()

        #网页浏览器
        args = [opt,mqtt_q_recv,mqtt_q_send]
        p = multiprocessing.Process(target=capture_webpage, args=(args,))
        jobs.append(p)
        p.start()

    try:
        # 主线程等待所有工作线程结束
        for j in jobs:
            j.join()
        print("所有线程已退出，程序结束。")
    except KeyboardInterrupt:
        # 此处作为备用，但通常 signal_handler 已处理
        pass
    finally:
        sys.exit(0)