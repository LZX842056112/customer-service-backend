# atguigu ecommerce service

这是一个配套 `atguigu` 项目使用的电商业务服务示例。

它提供：

- 用户最近订单 / 商品
- 订单状态查询
- 物流查询
- 商品信息查询
- 发货提醒创建
- 退款申请创建

初始化数据覆盖了多种典型状态，便于课堂演示：

- 待发货
- 待揽收
- 运输中
- 已完成
- 已取消
- 已有退款申请
- 已有发货提醒

## 启动方式

推荐直接使用 Docker Compose：

```powershell
cd atguigu_ecommerce_service
docker compose up --build
```

如果你之前已经启动过 MySQL 容器，并且数据库里已经写入了乱码数据，需要先清掉旧卷再重新初始化：

```powershell
docker compose down -v
docker compose up --build
```

启动后默认地址：

- API: `http://127.0.0.1:18081`
- OpenAPI: `http://127.0.0.1:18081/docs`

## 核心接口

- `GET /health`
- `GET /users/{user_id}/orders`
- `GET /users/{user_id}/products`
- `GET /orders/{order_id}`
- `GET /orders/{order_id}/status`
- `GET /orders/{order_id}/logistics`
- `GET /products/{product_id}`
- `POST /orders/{order_id}/shipping-reminders`
- `POST /orders/{order_id}/refund-applications`

## 本地开发

如果你本地装了 Python 和 MySQL，也可以自己跑：

```powershell
cd atguigu_ecommerce_service
uv sync
uv run uvicorn app.main:app --reload --port 18081
```

环境变量见 `.env.example`。
