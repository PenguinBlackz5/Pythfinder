CREATE TABLE IF NOT EXISTS user_gacha_characters (
    user_id BIGINT NOT NULL,
    character_name VARCHAR(100) NOT NULL,
    star INT NOT NULL,
    image_url TEXT NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    PRIMARY KEY (user_id, character_name, star, image_url)
); 