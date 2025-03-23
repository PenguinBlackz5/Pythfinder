from database_manager import execute_query


def init_database():
    try:
        with open('add_wallet.sql', 'r', encoding='utf-8') as file:
            sql_commands = file.read()

            for command in sql_commands.split(';'):
                if command.strip():
                    execute_query(command)

            print("데이터베이스 초기화가 완료되었습니다.")
    except Exception as e:
        print(f"데이터베이스 초기화 중 오류 발생: {e}")
        raise


if __name__ == '__main__':
    init_database()