-- 기존 데이터 삭제 (중복 방지)
DELETE FROM edmp.dm_dvc_mst;
DELETE FROM edmp.um_upd_sw_dvc_ver_map;
DELETE FROM edmp.ad_user_mst;

-- ad_user_mst 샘플 데이터 (user_co_fg_cd를 2자로 수정)
INSERT INTO edmp.ad_user_mst (user_id, user_nm, user_pwd, user_typ_fg_cd, user_co_fg_cd, user_email_addr, stm_fir_reg_date) VALUES
('admin', '관리자', 'hashed_pwd_1', '01', 'SK', 'admin@skbroadband.com', NOW()),
('tester1', '테스터1', 'hashed_pwd_2', '02', 'SK', 'tester1@skbroadband.com', NOW()),
('tester2', '테스터2', 'hashed_pwd_3', '02', 'PA', 'tester2@partner.com', NOW());

-- um_upd_sw_dvc_ver_map 샘플 데이터
INSERT INTO edmp.um_upd_sw_dvc_ver_map (modl_cd, modl_nm, stb_sw_ver, stb_sw_rst_ver, stm_fir_reg_user_id, stm_fir_reg_date, stm_last_upd_user_id, stm_last_upd_date) VALUES
('M001', 'UHD4-V1', '1.0.0.001', '1.0.0.001', 'admin', NOW(), 'admin', NOW()),
('M001', 'UHD4-V1', '1.1.0.002', '1.1.0.001', 'tester1', NOW(), 'tester1', NOW()),
('M002', 'V5-V2', '2.0.0.001', '2.0.0.001', 'admin', NOW(), 'admin', NOW());

-- dm_dvc_mst 샘플 데이터
INSERT INTO edmp.dm_dvc_mst (stb_id, stb_sw_ver, use_yn, stm_fir_reg_date, stm_fir_reg_user_id, team_cd) VALUES
('STB_001', '1.0.0.001', 'Y', NOW(), 'admin', 'TEAM_01'),
('STB_002', '1.1.0.002', 'Y', NOW(), 'tester1', 'TEAM_01'),
('STB_003', '2.0.0.001', 'Y', NOW(), 'admin', 'TEAM_02');
