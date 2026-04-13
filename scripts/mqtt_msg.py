import paho.mqtt.client as mqtt

def on_connect(client, userdata, flags, rc):
    """连接成功回调函数：订阅主题"""
    if rc == 0:
        print(f"连接成功，返回码 {rc}")
    else:
        print(f"连接失败，返回码 {rc}")


def on_message(client, userdata, msg):
    """消息接收回调函数：处理订阅到的消息"""
    mqtt_q = userdata
    payload = msg.payload.decode("utf-8")
    payload = payload.split(",")
    #print(f"收到消息：主题={msg.topic}，负载={payload}，QoS={msg.qos}")
    mqtt_q.put(payload)

    # 可在此处添加消息处理逻辑（如解析数据、存储到数据库等）

def mqtt_worker(args):
    # 创建MQTT客户端实例
    opt = args[0]
    mqtt_q_recv = args[1]
    mqtt_q_send = args[2]
    # 设置回调函数
    client = mqtt.Client(client_id=opt.mqtt_client_id, clean_session=True, userdata=mqtt_q_recv)
    client.on_connect = on_connect
    client.on_message = on_message

    # 设置认证信息（若需要）
    if opt.mqtt_usrname and opt.mqtt_password:
        client.username_pw_set(opt.mqtt_usrname, opt.mqtt_password)

    # 连接MQTT服务器
    try:
        client.connect(opt.mqtt_broker, opt.mqtt_port, keepalive=60)  # keepalive:心跳间隔（秒）
        # 订阅主题，QoS等级（0:最多一次，1:至少一次，2:恰好一次）
        client.subscribe(opt.mqtt_recv_ctrl_topic, qos=0)
    except Exception as e:
        print(f"连接服务器失败：{e}")
        return
    client.loop_start()  # 启动非阻塞的网络循
    while True:
        message = mqtt_q_send.get()
        #print(len(message))
        result = client.publish(opt.mqtt_send_screen_topic,bytearray(message), qos=0)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            print("消息发布失败")

    # 循环处理网络流量和回调（阻塞式，自动重连）
    #client.loop_forever()