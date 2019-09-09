        # # 业务处理：使用 python SDK 调用支付宝支付接口
        # # 初始化 设置配置，包括支付宝网关地址、app_id、应用私钥、支付宝公钥等，其他配置值可以查看AlipayClientConfig的定义。
        # alipay_client_config = AlipayClientConfig()
        # alipay_client_config.server_url = 'https://openapi.alipaydev.com/gateway.do' # 默认'https://openapi.alipay.com/gateway.do'
        # alipay_client_config.app_id = '2016101100663358' # 支付宝沙箱中的appid
        # alipay_client_config.app_private_key = os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem')
        # alipay_client_config.alipay_public_key = os.path.join(settings.BASE_DIR, 'apps/order/app_public_key.pem')
        # alipay_client_config.sandbox_debug = True

        # # 拿到客户端对象
        # client = DefaultAlipayClient(alipay_client_config=alipay_client_config)
        # # 调用支付接口
        # total_pay = order.total_price + order.transit_price # 带2位小数
        # # model = AlipayTradePagePayModel()  # 创建网站支付模型
        # model = AlipayTradePagePayModel()
        # model.out_trade_no = order_id # 订单id
        # model.total_amount = int(total_pay) # total_pay是带小数的，不能序列化，需要转成字符串
        # model.subject = '天天生鲜%s' % order_id
        # model.body = "支付宝测试"
        # model.product_code = "FAST_INSTANT_TRADE_PAY"

        # pay_request = AlipayTradePagePayRequest(biz_model=model) # 通过模型创建请求对象
        # pay_request.notify_url = None # 设置回调通知地址（POST）
        # pay_request.return_url = None # 设置回调通知地址（GET）

        # response = client.page_execute(pay_request, http_method="GET") # 获取支付链接
        # print("alipay.trade.page.pay response:" + response)

        # # 返回应答
        # return JsonResponse({'res': 3, 'response':response})