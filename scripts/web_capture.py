from playwright.sync_api import sync_playwright
from PIL import Image
import io
import time

def capture_webpage(args):
    opt=args[0]
    mqtt_q = args[1]
    mqtt_q_img = args[2]
    with sync_playwright() as p:
        # 启动浏览器（无头模式，不显示界面）
        browser = p.chromium.launch(headless=True)
        # 创建上下文，可设置User-Agent模拟真实浏览器
        context = browser.new_context(
            viewport={'width': opt.viewport_width, 'height': opt.viewport_height},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = context.new_page()

        # 导航到目标网页
        page.goto(opt.url)

        # 自动等待并填写用户名和密码
        # 设置认证信息（若需要）

        if opt.viewport_usrname and opt.viewport_password:
            page.fill('input[name="username"], input[id*="username"]', opt.viewport_usrname)  # 根据实际元素调整选择器
            page.fill('input[type="password"]', opt.viewport_password)  # 定位密码框
            try:
                page.get_by_role("button", name="登录").click()
            except:
                page.get_by_role("button", name="Log in").click()
        # 等待页面网络空闲状态，确保主要资源加载完成
        page.wait_for_load_state('networkidle')

        """
        todo 
        # **关键步骤：模拟滚动以触发懒加载图片**
        scroll_height = page.evaluate("document.body.scrollHeight")
        viewport_height = page.evaluate("window.innerHeight")
        current_position = 0
        while current_position < scroll_height:
            page.evaluate(f"window.scrollTo(0, {current_position})")
            page.wait_for_timeout(2000)  # 每次滚动后等待2秒，确保内容加载
            current_position += viewport_height
            # 动态内容可能导致页面高度增加
            scroll_height = page.evaluate("document.body.scrollHeight")
        """
        # 强制加载所有可能的懒加载图片
        #page.evaluate("""
        #    Array.from(document.querySelectorAll('img')).forEach(img => {
        #        if (img.dataset.src) img.src = img.dataset.src;
        #    });
        #""")
        #page.wait_for_timeout(2000)

        scroll_height =  opt.viewport_height
        # 根据最终页面高度设置视口大小，并进行全页截图
        page.set_viewport_size({"width": opt.viewport_width, "height": opt.viewport_height})
        count=0
        old_img_hash = 0

        scale_x = opt.viewport_width/(opt.touch_width*1.0)
        scale_y = opt.viewport_height/(opt.touch_height*1.0)
        print(f"start capture web:{opt.url} frame freq:{opt.send_hz} hz")
        while True:
            act_time = time.time()
            if(mqtt_q.empty() == False):
                buf = mqtt_q.get()
                '''
                buf format :  contor msg , x Coordinate , y Coordinate 
                e.g:
                    online,x,y (use first time)
                    update,120,332
                    update,100,200
                '''
                if len(buf) != 3:
                    print("bad touch screen coordinate len")
                elif buf[0] == "online":
                    '''
                    When the touch screen is powered on for the first time, 
                    an online message should be sent to obtain the first frame display
                    '''
                    old_img_hash = 0
                    print("touch screen online ...")
                elif buf[0] == "update":
                    try:
                        print(f"get mqtt contor:{buf[0]} x:{buf[1]} y: {buf[2]}")
                        buf[1] = int(buf[1])*scale_x
                        buf[2] = int(buf[2])*scale_y
                        print(f"send x:{buf[1]} y: {buf[2]}")
                        page.mouse.click(int(buf[1]), int(buf[2]), button="left")
                    except:
                        print("bad touch screen coordinate value")
                    #page.wait_for_load_state('networkidle')
                else:
                    print("bad touch screen coordinate")


            """
            todo
            # 使用evaluate执行JavaScript来检查body的样式
            body_style = page.evaluate('''() => {
                return document.body.getAttribute('style'); // 或检查className
            }''')
            if 'overflow: hidden' in (body_style or ''):
                print("检测到body样式变化，可能有弹窗。")
            """

            page.wait_for_load_state('networkidle')
            if opt.out_type == "file":
                write_path = opt.savedir + opt.savename + "_" + str(count) + ".jpg"
                page.locator('body').screenshot(path=write_path, type='jpeg', quality=90)  # 保存为JPEG格式
                print(f"网页截图保存至: {write_path} w: {opt.viewport_width} h: {opt.viewport_height}")
            elif opt.out_type == "mqtt":
                screenshot_bytes = page.locator('body').screenshot(type='jpeg', quality=95)

                '''
                scale web window -> screen window
                '''
                img = Image.open(io.BytesIO(screenshot_bytes))
                img_rsz = img.resize((opt.touch_width,opt.touch_height),Image.Resampling.LANCZOS)
                screenshot_bytes = io.BytesIO()
                img_rsz.save(screenshot_bytes, format='JPEG', quality=90)
                screenshot_bytes = screenshot_bytes.getvalue()

                this_img_hash = hash(screenshot_bytes)
                img_len = len(screenshot_bytes)
                #print("this img hash:", str(this_img_hash))
                if(this_img_hash != old_img_hash):
                    if(img_len > opt.send_buffer):
                        split_n = len(screenshot_bytes) // opt.send_buffer
                        for i in range(split_n):
                            mqtt_q_img.put(screenshot_bytes[i*opt.send_buffer:(i+1)*opt.send_buffer])
                        if len(screenshot_bytes) % opt.send_buffer:
                            mqtt_q_img.put(screenshot_bytes[split_n * opt.send_buffer:])
                    else:
                        mqtt_q_img.put(screenshot_bytes)
                    old_img_hash = this_img_hash

            elif opt.out_type == "multicas_udp":
                screenshot_bytes = page.locator('body').screenshot(type='jpeg', quality=90)
                #todo
            else:
                print("don`t support out_type:%s",opt.out_type)
            #screenshot_bytes = page.screenshot(path=write_path,full_page=True, type='jpeg', quality=90)  # 保存为JPEG格式
            #screenshot_bytes = page.screenshot(path=write_path,clip={'x': 10, 'y': 10, 'width': 800, 'height': 600}, type='jpeg', quality=90)  # 保存为JPEG格式
            time.sleep(1.0 / opt.send_hz)
            print(f"speed time:{str(time.time()-act_time)}")
            count = count + 1
        browser.close()