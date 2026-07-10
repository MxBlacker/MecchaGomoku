# MecchaGomoku v 0.1
游戏还在测试中...

>🎶传统的五子棋🧐就是把五个子🫥连成一条线🥸好无趣😩好无聊😫而技能五子棋🤓☝🏻就是在传统的五子棋🤗加入技能好好玩🤪💥💥🤯要爆了!!!🤩💥💥

超级五子棋（Meccha Gomoku）是一款基于 Pygame 开发的五子棋小游戏，包含单人对战，多人局域网联机，人机对战和技能五子棋等功能，支持对局回放，AI解析和个性化设置。

下面是技术栈：

- UI：GPT Image 2 + 豆包 + Photoshop 抠图
- 界面层：Pygame（UI绘制，事件处理，游戏主循环）
- 游戏逻辑：Python原生
- AI：[Rapfi-AI](https://github.com/dhbloo/rapfi)
- 网络层：WebSocket + HTML
- 数据层：json（保存对局数据）

### 使用说明

clone到本地后，运行 `main.py` 即可

```bash
git clone ...
python ./main.py
```

如果需要棋局回放和AI解析的功能，请在 `config.py` 中输入自己的 API keys

***
感谢 Claude code 和 deepseek4.0 的大力支持（膜拜

