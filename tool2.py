import os


def list_all_paths(target_folder):
    """遍历目标文件夹，输出所有文件和文件夹的名称（含相对路径）"""

    if not os.path.exists(target_folder):
        print(f"错误：路径不存在 - {target_folder}")
        return

    if not os.path.isdir(target_folder):
        print(f"错误：目标路径不是文件夹 - {target_folder}")
        return

    print(f"正在遍历：{target_folder}\n")
    print("=" * 60)

    for root, dirs, files in os.walk(target_folder):
        # 计算相对于目标文件夹的路径
        rel_path = os.path.relpath(root, target_folder)
        if rel_path == ".":
            rel_path = ""  # 根目录

        # 输出当前文件夹名（相对于目标文件夹）
        folder_display = f"[文件夹] {rel_path}" if rel_path else "[根文件夹]"
        print(folder_display)

        # 输出当前文件夹下的所有子文件夹名（直接子级）
        for dir_name in dirs:
            sub_dir_path = os.path.join(rel_path, dir_name) if rel_path else dir_name
            print(f"  [子文件夹] {sub_dir_path}")

        # 输出当前文件夹下的所有文件名
        for file_name in files:
            file_path = os.path.join(rel_path, file_name) if rel_path else file_name
            print(f"  [文件] {file_path}")

    print("=" * 60)
    print("遍历完成")


def get_all_items_as_list(target_folder):
    """返回两个列表：所有文件夹路径列表、所有文件路径列表（相对路径）"""

    folders = []
    files = []

    for root, dirs, file_names in os.walk(target_folder):
        rel_root = os.path.relpath(root, target_folder)
        if rel_root == ".":
            rel_root = ""

        # 添加当前文件夹（除非是根目录本身）
        if rel_root:
            folders.append(rel_root)

        # 添加子文件夹（可选，如果只要顶层子文件夹可注释）
        for dir_name in dirs:
            sub_dir = os.path.join(rel_root, dir_name) if rel_root else dir_name
            folders.append(sub_dir)

        # 添加文件
        for file_name in file_names:
            file_rel = os.path.join(rel_root, file_name) if rel_root else file_name
            files.append(file_rel)

    return folders, files


# ========== 使用示例 ==========
if __name__ == "__main__":
    # 请修改为你要遍历的目标文件夹路径
    target_path = r"C:\Users\Ni339\Documents\MuMu共享文件夹\Asset"  # Windows 示例
    # target_path = "/home/user/Documents"   # Mac/Linux 示例

    # 方式一：直接打印输出
    list_all_paths(target_path)

    # 方式二：获取列表后再处理
    # folder_list, file_list = get_all_items_as_list(target_path)
    # print("\n所有文件夹：")
    # for f in folder_list:
    #     print(f"  {f}")
    # print("\n所有文件：")
    # for f in file_list:
    #     print(f"  {f}")