# 记录

使用python环境为3.7.6，环境配置使用anaconda。安装了pygame，requests。
解决了之前的麻将游戏遇到的，enter按键，左右按键多次触发的问题，现在需要做的是把ai工具尝试与麻将游戏对接起来。
现在的问题是：
1.不知道怎么能够知道全局的牌面，只知道player.py中的draw_screen中的self.concealed_str，self.exposed_str，self.desk_str都是只有当前麻将的手牌，名牌（碰，杠，已经打在桌上的牌）