# Markdown 图片本地化工具
一个用于扫描 Markdown 文件、下载外部图片并替换本地链接的 Python 脚本。多线程下载，并提供多种图片命名方式。

## 主要功能
+ 扫描 Markdown 文件：递归遍历指定目录下的所有 Markdown (.md) 文件。
+ 识别外链图片：解析 Markdown 内容中的外部图片链接（http:// 或 https:// 开头）。
+ 下载图片到本地：将识别到的外部图片下载到 Markdown 文件同级目录下的独立文件夹中。
+ 替换图片链接：将 Markdown 文件中的外部图片链接替换为本地相对路径。
+ 多种图片命名模式：支持使用原始文件名、UUID 或递增序号来命名下载的图片。
+ 多线程并发下载：利用多线程提高图片下载效率。
+ 详细日志记录：将主程序运行日志和图片下载日志分别记录到独立的文件中。
+ 清理空图片目录：处理完成后自动删除不再包含图片的空目录。



## 如何配置
在脚本的 `main()` 函数中，可以找到以下重要配置项：

> 设置并发数时，需要注意外链服务器可能因频繁访问触发限流策略，所以并发数最好不超过3不然秒封
>

```plain
def main():
    # 配置项1：目标目录路径(支持多层目录)
    target_root_path = 'C:/Users/xxx/' 
    
    # 配置项2：图片命名模式: 'original' (原始文件名), 'uuid' (随机UUID), 'asc' (递增序号)
    image_rename_mode = 'original' 
    
    # 配置项3：最大并发下载线程数
    max_threads = 4 
```



## 如何运行
### 方式一：通过命令行运行
1. 执行命令导入`requests`库(只有这一个第三方库)：
```plain
pip install requests
```
3. 保存脚本为 `your_script_name.py` (例如：`md_image_localizer.py`)
4. 打开命令行或终端，导航到脚本所在的目录，执行以下命令：

```plain
python your_script_name.py
```



### 方式二：通过 PyCharm 运行
1. 点 ▶  





## 日志文件
脚本会在 `target_root_path` 目录下生成两个日志文件：

+ `yuque_processor_main.log`：记录主程序的运行信息、文件处理进度等。
+ `yuque_processor_downloads.log`：记录每张图片的下载成功或失败信息。

