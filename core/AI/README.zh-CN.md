# Rapfi 整合包 使用说明

> 最后更新时间：2025.06.15

[toc]

## 简介

Rapfi是一个[免费开源](https://github.com/dhbloo/rapfi)的五子棋引擎，采用Alpha-Beta搜索算法和NNUE小型神经网络技术，具有较强的棋力。其在CPU上运行，不使用显卡GPU等其他资源；在核心数量越多、性能越强的CPU上运行一般有着更强的棋力。

目前NNUE支持的规则和棋盘大小包括：

+ 无禁13~21路（Freestyle 13-21）
+ 六不赢15路（Standard 15）
+ 有禁手15路（Renju 15）

使用以上规则和棋盘将开启NNUE；其他规则和棋盘大小将采用传统估值，此时的棋力会低于其他开启NNUE规则和棋盘大小下的棋力。

引擎本身不含有开局知识，默认采用自由开局下法，不包含对其他开局下的对弈支持。如有需要，可以自行摆放开局，并使用引擎的“一手平衡”即“二手平衡”功能计算平衡局面。



### 五子棋计算器（网页版）

如果你想在手机上体验类似的棋力，欢迎使用网页版五子棋计算器：[gomocalc.com](https://gomocalc.com)

该网站同样采用Rapfi引擎与小型权重，其可以在任何支持浏览器的设备上使用。为了最佳的性能，推荐使用Chrome/Edge/Firefox/Safari浏览器打开。



## 整合包说明

本整合包含有3个部分：Rapfi引擎核心，Rapfi+Yixin界面，以及Rapfi制谱器。

### Rapfi引擎核心

引擎核心仅包含引擎本体，不包含图形界面，可以通过命令行的方式进行交互，具体请参考[五子棋Piskvork协议](http://petr.lastovicka.sweb.cz/protocl2en.htm)。该版本适合用于[Piskvork](https://sourceforge.net/projects/piskvork/)、[c-gomoku-cli](https://github.com/nkg114mc/c-gomoku-cli)等比赛管理器进行AI之间比赛。

引擎运行需要64位Windows/Linux/MacOS操作系统，共多个指令集版本。

对于AMD64/x86-64 CPU，根据理论速度推荐使用的排序为：

**AVX512VNNI > AVX512 > AVXVNNI > AVX2（默认） > SSE**。

对于Arm64/Armv8a CPU，根据理论速度推荐使用的排序为：

**NEON_DOTPROD > NEON**

根据你的CPU支持的指令集不同，请选择合适的指令集版本以获得最优的计算速度。（具体CPU支持的指令集版本可以使用CPU-Z软件查看；此外如果在使用时无法启动对应指令集版本的引擎，也能判断出该CPU不支持此指令集）

使用时注意复制全部文件，包括config和每个权重，缺少任何文件引擎将无法启动，或者产生其他错误。建议将引擎文件置于纯英文路径下运行，虽然中文路径下也能使用，但不排除可能出现什么其他问题。



### Rapfi+Yixin界面

适合有对弈或者对局面的快速计算有需求的用户使用。运行时，打开`Yixin.exe`图形界面即可。

#### Yixin界面设置简介

目前在Yixin界面中，Rapfi最高支持设置256线程与1TB内存。

Yixin界面的其他使用方法请参考[Yixin界面说明文档](https://www.aiexp.info/pages/yixin-docs-cn.html)。

#### 如何启用NBEST多点分析功能

如果需要让Rapfi同时输出多于1个选点以上的分数，可以使用NBEST功能（在Yixin界面右下侧的文本框输入`best [number]`并回车，其中`number`为需要分析的点的数量。如`nbest 4`表示让引擎同时完整分析4个最佳点并输出它们的估值结果）。新版本可在设置选择需要的多点分析数量，并点击多点分析按钮。

注意NBEST功能虽然能够更全面的分析选点，但其会导致同时间内搜索深度降低，从而引起综合棋力有所下降。

#### 一些使用提示

+ **如果Yixin界面中的引擎无法启动，可能是你的CPU较老不支持AVX2，需要把Rapfi引擎目录下的`pbrain-rapfi_windows_sse.exe`替换掉本目录下的`engine.exe`文件。**
+ **对于12代之后的Intel CPU，推荐替换AVXVNNI引擎；对于AMD RYZEN 7000系（ZEN4）之后的CPU，推荐替换AVX512VNNI引擎，以获取最佳速度**
+ 对于线程数设置，保守情况下最少可以设置为你的CPU的核心数大小；对于有超线程的CPU，一般推荐设置为核心数量的1.6~2.0倍，能够更好的利用超线程带来的效率提高。（例如，10核多线程CPU的最佳线程数大约是16~20）
+ 对于哈希表大小，建议根据你的电脑内存大小进行合理设置。通常来说，更大的置换表能够在长时间的计算中表现更快。一般线程数量越大需要更大的置换表以保证搜索效率。推荐每个线程至少对应**2GB**的置换表大小（假设你使用4线程，则推荐的置换表大小至少为4x2=8GB）。
+ Yixin界面设置中的“仅计算VCT”、“仅计算VC2”功能暂未支持，目前设置它们不会有任何效果。
+ 后台思考适用于有限时间下的对弈模式，当引擎完成分析某一步时，其会自动在后台继续下一步的计算，期间不会有任何提示输出。对于分析模式（不限时），后台思考不会开启。
+ 可以在`function/toolbar*.txt`中修改侧边栏各个按钮的对应命令（也可以在界面输入`toolbar edit [序号]`编辑）；在`function/hotkey*.txt`中修改快捷键对应的命令（也可以在界面输入`key edit [序号]`编辑）。
+ 可以在`settings.txt`中修改界面使用的字体（以及字号）；字体名称需要使用英文（中文字体所对应的英文名称可以在[这里](https://www.zhangxinxu.com/wordpress/2017/03/css-font-family-chinese-english/)找到）

#### 棋谱数据库

棋谱数据库功能可以让Rapfi读写棋谱文件，自动记录引擎计算结果，并在以后的计算中直接读取相关记录以加速搜索分析过程，从而实现保留计算结果和局面研究的功能。目前Rapfi目前支持读取和保存Yixin DB棋谱数据库文件格式，其与Yixin棋谱格式兼容，支持直接打开任意的Yixin棋谱。目前数据库的绝大部分功能均可以配合经过修改的Yixin界面使用，通过界面上的按钮完成。

+ 开启数据库：在界面左上角勾选启用数据库。开启数据库后引擎会搜索棋谱信息(此时棋谱质量会影响搜索结果，若棋谱质量不好，搜索结果会有问题，此时可以考虑关闭数据库功能进行计算。
+ 数据库记录：若启用数据库功能，在引擎的计算过程中，引擎会将计算结果，按照配置文件所规定的记录条件，记录或更新到棋谱数据库中。通过自行调整数据库记录和更新条件，可以实现不同细节程度的数据库记录功能。如需修改棋谱记录的详细程度，可以修改配置文件，请参考[配置文件说明](#配置文件)。自动记录的数据库标记分为必胜(如`W31`)，必败(如`L42`)和胜率分数(如`50%`)3种类型。
+ 只读模式：在界面左上角勾选数据库只读模式后，针对数据库的自动修改，如搜索记录和点击记录，将被关闭。
+ 数据库文件的读取与保存：在界面中选择“新建棋谱”按钮可以创建一个空白数据库；选择“打开棋谱”可以打开现有棋谱；选择“保存棋谱”可以将所有修改保存到当前打开的棋谱中。
+ 查看估值：选择“数据库估值”按钮或输入`dbval`命令可以查看当前局面的数据库估值记录。
+ 分支删除：Yixin界面中加入了各类常用的删除模式。需要注意的是，对于分支删除，可能**会有一些被共享的分支在当前局面下不会被删除**，这是因为其被其他局面的分支依赖，因此为了保存完整性，引擎只会删除完全不存在父局面的分支。如果你发现没能被删全的分支，则可以退回到上一级局面再进行删除。
+ 棋盘文字标记：开启数据库后，用**鼠标中间**点击、或**按住键盘Control键**用鼠标左键点击棋盘空位，可以编辑当前空位的棋盘文字，不超过3个中文字符或6个英文字符。若空位有棋盘文字标记，则只显示棋盘文字标记，其原有的胜负估值标记将不显示。在Yixin界面显示菜单下可以切换是否显示棋盘文字。
+ 盘面注释：对于每个局面，可以在右侧的注释编辑框中查看对该局面的注释，并可以随时修改该注释。
+ 数据库合并与拆分：
  + 合并功能将其他的数据库文件内容合并到当前打开的数据库中，如果两个文件中含有同样局面的不同记录，按照保留更重要的记录原则对当前打开的数据库进行更新
  + 拆分功能将当前局面分支保存到另外一个数据库文件中，可用于单独分支的保存
+ Lib棋谱导入：Renlib棋谱文件(`.lib`)可以通过本功能导入到当前打开的数据库中，使得Lib棋谱可以被方便地转化为DB数据库。Lib棋谱中原有的棋盘文字标记和盘面注释将被一同导入，若不需要导入注释，可以在配置文件中关闭。部分特殊的标记将被转化为DB数据库的胜负标记和分数标记：
  - 必胜标记：`a`标记和`W`标记(包括`W41`之类的带步数标记)将被转化为`W`数据库标记，其中`a`标记可以在配置文件中修改为其他标记。
  - 必败标记：`c`标记和`L`标记(包括`L39`之类的带步数标记)将被转化为`L`数据库标记，其中`c`标记可以在配置文件中修改为其他标记。
  - 分数标记：`v`标记和`m`标记(如`v42`和`m130`)的分数将被转化为数据库胜率标记
  - 单字符标记：对于其他的单字符棋盘标记，将被直接记录到数据库标记中，对于其他的多字符Lib棋谱标记，其将会被记录到数据库的注释中。

棋谱数据库配置示例：

+ 扫描一层，保留必胜必败招法（与Yixin、终结者配置相同）

  ```toml
  pv_write_ply = 0					# 主要分支下数据库最大写入层数
  pv_write_min_depth = 25				# 主要分支下数据库允许写入的最低搜索深度
  write_value_range = 800				# 主要分支/非主要分支下数据库允许写入的最大分数范围
  mate_write_ply = 2					# 必胜必败分支下数据库最大写入层数
  mate_write_min_depth_exact = 0		# 准确步数的必胜必败分支下数据库允许写入的最低搜索深度
  mate_write_min_depth_nonexact = 0	# 没有得到准确步数的必胜必败分支下数据库允许写入的最低搜索深度
  mate_write_min_step = 0				# 必胜必败下数据库允许写入的最低必胜必败步数
  ```

+ 详细地毯所有分支防守点直到最简杀

  ```toml
  pv_write_ply = 0					# 主要分支下数据库最大写入层数
  pv_write_min_depth = 25				# 主要分支下数据库允许写入的最低搜索深度
  write_value_range = 800				# 主要分支/非主要分支下数据库允许写入的最大分数范围
  mate_write_ply = 100				# 必胜必败分支下数据库最大写入层数
  mate_write_min_depth_exact = 20		# 准确步数的必胜必败分支下数据库允许写入的最低搜索深度
  mate_write_min_depth_nonexact = 30	# 没有得到准确步数的必胜必败分支下数据库允许写入的最低搜索深度
  mate_write_min_step = 10			# 必胜必败下数据库允许写入的最低必胜必败步数
  ```

+ 拆平衡混搭极简必胜

  ```toml
  pv_write_ply = 100					# 主要分支下数据库最大写入层数
  pv_write_min_depth = 25				# 主要分支下数据库允许写入的最低搜索深度
  write_value_range = 800				# 主要分支/非主要分支下数据库允许写入的最大分数范围
  mate_write_ply = 2					# 必胜必败分支下数据库最大写入层数
  mate_write_min_depth_exact = 0		# 准确步数的必胜必败分支下数据库允许写入的最低搜索深度
  mate_write_min_depth_nonexact = 0	# 没有得到准确步数的必胜必败分支下数据库允许写入的最低搜索深度
  mate_write_min_step = 0				# 必胜必败下数据库允许写入的最低必胜必败步数
  ```

+ 极简模式

  ```toml
  pv_write_ply = 2					# 主要分支下数据库最大写入层数
  pv_write_min_depth = 25				# 主要分支下数据库允许写入的最低搜索深度
  write_value_range = 800				# 主要分支/非主要分支下数据库允许写入的最大分数范围
  mate_write_ply = 0					# 必胜必败分支下数据库最大写入层数
  mate_write_min_depth_exact = 0		# 准确步数的必胜必败分支下数据库允许写入的最低搜索深度
  mate_write_min_depth_nonexact = 0	# 没有得到准确步数的必胜必败分支下数据库允许写入的最低搜索深度
  mate_write_min_step = 0				# 必胜必败下数据库允许写入的最低必胜必败步数
  ```

+ 通过步数和层数控制：记录深度20之后的强防与深度30之后的弱防，并要求不记录所有30步杀以内的杀棋

  ```toml
  pv_write_ply = 0					# 主要分支下数据库最大写入层数
  pv_write_min_depth = 25				# 主要分支下数据库允许写入的最低搜索深度
  write_value_range = 800				# 主要分支/非主要分支下数据库允许写入的最大分数范围
  mate_write_ply = 100				# 必胜必败分支下数据库最大写入层数
  mate_write_min_depth_exact = 20		# 准确步数的必胜必败分支下数据库允许写入的最低搜索深度
  mate_write_min_depth_nonexact = 30	# 没有得到准确步数的必胜必败分支下数据库允许写入的最低搜索深度
  mate_write_min_step = 30			# 必胜必败下数据库允许写入的最低必胜必败步数
  ```




#### 进阶功能：如何在Yixin界面中修改最大步数与和棋结果

> 本节适合需要使用高级功能的用户，普通用户可以直接跳过本节说明。

Rapfi支持设置最大步数至和棋（`max_moves`功能），和调节和棋结果（`draw_result`、`evaluator_draw_black_winrate`、`evaluator_draw_ratio`功能）。这些功能可以通过在Yixin界面中手动输入命令开启或关闭。

需要注意的是，**最大步数与和棋结果的修改可能会对数据库的结果导致影响**，使用前请先切换到新的数据库文件，或关闭数据库功能。

一些使用用例：

+ 限制最大步数为31，和棋平局：

  ```
  command on
  info max_moves 31
  info draw_result 0
  info evaluator_draw_black_winrate 0.5
  info evaluator_draw_ratio 1.0
  command off
  ```

+ 限制最大步数为33，和棋黑胜，同时将评估的和棋率设置为0：

  ```
  command on
  info max_moves 33
  info draw_result 1
  info evaluator_draw_black_winrate 0.5
  info evaluator_draw_ratio 0.0
  command off
  ```

+ 限制最大步数为35，和棋白胜，同时调整评估的结果至和棋白胜（黑棋胜率0）：

  ```
  command on
  info max_moves 35
  info draw_result 2
  info evaluator_draw_black_winrate 0.0
  info evaluator_draw_ratio 0.0
  command off
  ```




## 引擎详细说明

> 本节适合需要使用高级功能的用户，普通用户可以直接跳过本节说明。

### 配置文件

Rapfi的各项配置由名为`config.toml`的TOML文件管理。部分常用配置说明如下：

+ 通用配置
  + `reload_config_each_move`：是否每步棋都重新载入配置文件
  + `clear_hash_after_config_loaded`：是否在载入配置文件后清空置换表
  + `message_mode`：消息输出模式，选项包括
    + `normal`：普通、
    + `brief`：简略、
    + `ucilike`：类似于UCI协议，与胚胎输出格式相同
    + `none`：关闭所有消息输出
  + `coord_conversion_mode`：坐标转换模式，选项包括
    + `none`：不转换（适用于Piskvork界面）
    + `X_flipY`：翻转Y轴
    + `flipY_X`：翻转Y轴并交换X轴与Y轴（适用于Yixin界面与制谱器）
  + `default_candidate_range`：默认选点范围（此项可以用Yixin界面中的“棋风”选项调节），选项包括
    + `square2`（Yixin棋风0）：两圈
    + `square2_line3`（Yixin棋风1）：两圈半，早期版本常用选项
    + `square3`（Yixin棋风2）：三圈
    + `square3_line4`（Yixin棋风3）：**三圈半，目前推荐选项**
    + `full_board`（Yixin棋风4）：全盘选点，最严格的必胜证明
  + `memory_reserved_mb`：对`info max_memory`选项预留内存空间；该项用于防止引擎在Piskvork等对战软件中超出内存限制
  + **`default_tt_size_kb`**：默认的置换表大小（KB）；*在制谱器中请使用这个配置修改需要使用的内存大小*
+ 评估模型配置
  + `scaling_factor`：分数胜率换算比例（默认取值2.0，不建议修改）
  + `type`：评估器类型（目前只有`mix6nnue`）
  + `wlr_mate_value`：边界胜率。某一方超过该胜率后，评估为最大值（+/- 20000）
  + `draw_black_winrate`：和棋时的黑棋胜率，值在[0, 1]之间（默认0.5）
  + `draw_ratio`：和棋比率，值在[0, 1]之间（默认1.0）；若设置为0，则表示和棋率为0；若设置为`r`，则表示和棋率为`真实和棋率 * r`。
+ 搜索配置
  + `aspiration_window`：是否启用期望窗口（推荐开启）
  + `num_iteration_after_mate`：算杀后继续计算多少个迭代，默认为20
  + `num_iteration_after_singular_root`：发现唯一着法后继续计算多少个迭代，默认为10
+ 数据库配置
  + `enable_by_default`：是否自动开启数据库
  + `type`：数据库类型
  + `url`：数据库默认路径
  + Yixin DB 配置
    + `compressed_save`：数据库是否采用压缩格式保存 (非压缩格式下保存的数据库可以使用Yixin打开)
    + `save_on_close`：数据库关闭时是否保存
    + `num_backups_on_save`：数据库保存时保留备份的个数
    + `ignore_corrupted`：允许读取部分损坏的数据库
  + 数据库记录设置
    + `readonly_mode`：开启数据库只读模式，开启后不会写入新的搜索结果到数据库
    + `query_ply`：数据库最少查询层数，默认为3
    + `pv_iter_per_ply_increment`：主要分支下数据库查询层数增加相隔搜索深度，默认为1
    + `nonpv_iter_per_ply_increment`：非主要分支下数据库查询层数增加相隔搜索深度，默认为2
    + 以下4个选项控制路线记录的程度：
      + **`pv_write_ply`**：主要分支下数据库最大写入层数，默认为1。增大该层数可以保留更多层主要路线下的胜率结果
      + **`pv_write_min_depth`**：主要分支下数据库允许写入的最低搜索深度，默认为25
      + `nonpv_write_ply`：非主要分支下数据库最大写入层数，默认为0（不建议修改）
      + `nonpv_write_min_depth`：非主要分支下数据库允许写入的最低搜索深度，默认为25（不建议修改）
    + 以下4个只控制必胜必败地毯的精细程度：
      + **`mate_write_ply`**：必胜必败分支下数据库最大写入层数，默认为2，增大该层数可以保留更多层的必胜必败结果
      + `mate_write_min_depth_exact`：准确步数的必胜必败分支下数据库允许写入的最低搜索深度，默认为20
      + `mate_write_min_depth_nonexact`：没有得到准确步数的必胜必败分支下数据库允许写入的最低搜索深度，默认为40
      + `mate_write_min_step`：必胜必败下数据库允许写入的最低必胜必败步数，默认为10，少于该步数的必胜必败将不会被记录
    + `exact_overwrite_ply`：准确分值允许覆盖数据库的层数，默认为100
    + `nonexact_overwrite_ply`：非准确分值允许覆盖数据库的层数，默认为0
    + `overwrite_rule`：数据库覆盖模式，选项包括[better_value_depth_bound, better_depth_bound, better_value, better_label, always, disabled]。默认为better_value_depth_bound，不建议修改
    + `overwrite_exact_bias`：准确分数的深度加成，默认为3
    + `overwrite_depth_bound_bias`：旧记录的深度加成，默认为-1
    + `query_result_depth_bound_bias`：查询结果记录的深度加成，默认为0
  + Lib导入设置
    + `black_win_mark`、`white_win_mark`、`black_lose_mark`、`white_lose_mark`：分别控制Lib中黑胜、白胜、黑败、白败对应的棋盘文字标记。
    + `ignore_comment`：导入时是否忽略注释


### 高级命令与选项

根据[Piskvork协议](http://petr.lastovicka.sweb.cz/protocl2en.htm)，用户程序可以通过`INFO options [value]`向引擎发送配置选项。Rapfi除了支持基础的Piskvork选项，还支持[Yixin-Board扩展选项](https://github.com/accreator/Yixin-protocol)。

此外，Rapfi还支持通过此方式向引擎发送额外选项，以开启部分高级功能。选项的优先级高于配置文件，因此如果选项取值不同于配置文件中的取值，将采用选项取值。

+ `INFO caution_factor [value]`：设置选点范围。`value`取值为{0, 1, 2, 3, 4}中的一个，分别对应两圈选点、两圈半选点、三圈选点、三圈半选点、全盘选点
+ `INFO strength [value]`：设置棋力限制。`value`取值范围是[0, 100]中的整数，其中100表示不限制棋力，0表示最大程度限制棋力。默认值为100
+ `INFO max_moves [value]`：设置最大步数，超过该步数后，若仍为分出胜负，则按照判和规则进行和棋判断。`value`取值`-1`表示关闭该功能
+ `INFO draw_result [value]`：设置和棋胜负判定。`value`取值为{0, 1, 2}分别表示和棋平局、黑胜、白胜
+ `INFO evaluator_draw_black_winrate [value]`：设置评估的和棋黑棋胜率，`value`在[0, 1]之间（默认0.5）
+ `INFO evaluator_draw_ratio [value]`：设置评估的和棋比率，`value`在[0, 1]之间（默认1.0）；若设置为0，则表示和棋率为0；若设置为`r`，则表示和棋率为`真实和棋率 * r`。

### 命令行启动

Rapfi支持在命令行启动时设置配置文件，如用`pbrain-rapfi_avx2.exe --config=myconfig.toml`启动，可以使用当前目录下的`myconfig.toml`替代原始的配置文件。对于支持的命令行选项，可以使用`pbrain-rapfi_avx2.exe --help`进行查看。



## 更新日志

2025.06.15

+ 更新nnue结构，大幅减少权重大小，综合elo提高
+ 改进引擎在多CPU机器上的性能，修复数据库的部分问题
+ Yixin界面更新到GTK3，支持MacOS，支持Unicode（Emoji）输入，更多语言支持
+ 加入实时思考胜率显示、多点分析按钮、黑暗主题切换等便捷功能

2024.06.08

+ 更新nnue结构，综合elo提高
+ 新增AVXVNNI、AVX512VNNI、ARM64-NEON、ARM64-NEON-DOTPROD版本引擎
+ Yixin界面支持设置界面字体

2023.09.02

+ 更新nnue结构以及引擎优化，综合elo提高
+ 新增AVX512版本引擎
+ 数据库内文本改用utf-8编码储存

2023.06.13

+ 引擎优化
+ 修复一些bug

2023.01.12

+ 引擎优化，elo提高
+ Yixin界面加入数据库棋盘文字标记功能
+ Yixin界面加入数据库盘面注释功能
+ Yixin界面加入棋盘代码框与复制粘贴快捷键
+ 优化Yixin界面数据库保存，增加保存提示
+ Yixin界面其他小优化

2022.10.10

+ 修复可能导致错误算杀的防点bug
+ 修复导致错误算杀步数的bug
+ 增加数据库分类删除功能

2022.09.17

+ 支持数据库功能
  - 支持`.db`文件格式读取与保存，兼容Yixin DB数据库
  - 支持自动记谱功能
  - 支持数据库拆分，合并，导入Lib棋谱文件
+ 引擎小幅更新

2022.08.28

+ 更新nnue结构，综合elo提高
+ 修复连珠规则下某些局面的招法生成bug
+ 支持自动开启Windows Large Page

2022.06.10

+ 修复有禁的着法生成错误
+ 根节点自动筛选对称选点
+ 支持调整选点范围
+ 支持`max_moves`选项调整最大步数至和棋、`draw_result`选项调整和棋胜负判断
+ 支持`evaluator_draw_black_winrate`和`evaluator_draw_ratio`选项调整评估和棋胜率与和棋比率
+ 支持非2次幂的置换表大小
+ 综合ELO提高



## 关于

**本软件始终保持开源免费！** 如果你在其他平台看到有人在贩卖本软件，其均非作者所为，我们不鼓励二次贩卖行为。

**获取最新版软件，以及反映使用问题，请加入 Rapfi 软件交流QQ群：669067795。我们也有一个[Discord频道](https://discord.gg/7kEpFCGdb5)。**



### 赞助

引擎与界面在开发过程中需要用到较多的时间精力与机器的硬件成本（在训练与测试中会需要租用大量的CPU与GPU、以及提供网页版服务的服务器开销）。

实际上，在过去的几年中，用于Rapfi开发与网页版五子棋计算器维护的各类硬件成本累积已经超过了6000RMB。在可见的未来，进一步提升棋力与增加新功能将会需要持续的资源投入。

**如果你觉得本软件对你有帮助，并且喜欢看到更多新功能的开发与更新，欢迎对本项目进行打赏赞助。**

你的捐赠将极大地帮助引擎的进一步提高，并且帮助各类新功能的开发。



### 鸣谢

本引擎主要作者：

+ dblue (https://github.com/dhbloo)，QQ: 1084714805
+ sigmoid (https://github.com/hzyhhzy)，QQ: 2658628026

完整作者列表请参考AUTHORS文件 (https://github.com/dhbloo/rapfi/blob/master/AUTHORS)

感谢所有提供过引擎改进建议与bug报告的贡献者，此处不再详细列出。