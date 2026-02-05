                            
                            # ========================================
                            # 邊界線過濾與 Two-Band Filter 整合
                            # ========================================
                            image_height = self.st_frame_info.nHeight
                            image_width = self.st_frame_info.nWidth
                            
                            # 計算邊界線的像素位置
                            top_line_y = int(image_height * boundary_line_top)
                            bottom_line_y = int(image_height * boundary_line_bottom)
                            
                            # --- 1. Two-Band Filter 觸發系統處理 (如果啟用) ---
                            if self.enable_trigger_system and self.tracker is not None and self.two_band_filter is not None:
                                try:
                                    # 即時更新 Two-Band Filter 的區域位置 (同步 UI 設定)
                                    self.two_band_filter.trigger_zone_top = top_line_y
                                    self.two_band_filter.trigger_zone_bottom = bottom_line_y
                                    self.two_band_filter.confidence_threshold = conf_thres

                                    # 物體追蹤
                                    tracker_results = self.tracker.update(results)
                                    
                                    # 轉換格式給 Two-Band Filter
                                    filter_input = [
                                        (track_id, np.concatenate([bbox, [conf, cls]]))
                                        for track_id, bbox, conf, cls in tracker_results
                                    ]
                                    
                                    # 處理每一幀並判斷觸發
                                    filter_result = self.two_band_filter.process_frame(
                                        detections=results,
                                        tracker_results=filter_input
                                    )
                                    
                                    # 檢查觸發結果 (僅用於 Debug Log)
                                    if filter_result.get('triggered_this_frame'):
                                        triggered_count = len(filter_result['triggered_this_frame'])
                                        print(f"[TriggerSystem] Triggered {triggered_count} objects this frame")
                                        for trigger in filter_result['triggered_this_frame']:
                                            print(f"  → Track {trigger['track_id']}: Class={trigger['class_id']}, Conf={trigger['confidence']:.2f}")

                                except Exception as e:
                                    print(f"[TriggerSystem] Error in Two-Band Filter processing: {e}")
                                    import traceback
                                    traceback.print_exc()

                            # --- 2. 邊界線過濾與 TCP 傳送 ---
                            filtered_boxes = []
                            all_boxes_count = 0
                            
                            if results and hasattr(results[0], 'boxes') and len(results[0].boxes) > 0:
                                all_boxes_count = len(results[0].boxes)
                                if boundary_filter_enabled:
                                    # 啟用過濾：只保留觸碰到邊界線的物件
                                    filtered_boxes = filter_detections_by_boundary(results, image_height)
                                else:
                                    # 未啟用過濾：保留所有物件
                                    for box in results[0].boxes:
                                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                                        cls = int(box.cls.item())
                                        conf = float(box.conf.item())
                                        filtered_boxes.append((cls, int(x1), int(y1), int(x2), int(y2), conf))
                            
                            # 發送辨識結果到 TCP 服務器
                            if get_tcp_server is not None:
                                tcp_server = get_tcp_server()
                                if tcp_server and len(filtered_boxes) > 0:
                                    # 只有當有符合條件的物件時才傳送
                                    tcp_server.send_filtered_detection_result(
                                        filtered_boxes,
                                        image_width, 
                                        image_height
                                    )
                                elif tcp_server and not boundary_filter_enabled:
                                    # 未啟用過濾時，正常傳送所有結果
                                    tcp_server.send_detection_result(
                                        results, 
                                        image_width, 
                                        image_height
                                    )

                            # 準備辨識結果文字
                            detection_text_result = f"Frame: {self.st_frame_info.nFrameNum}\n"
                            detection_text_result += f"Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n"
                            detection_text_result += "------------------------------------\n"
                            detection_text_result += f"邊界線過濾: {'啟用' if boundary_filter_enabled else '停用'}\n"
                            detection_text_result += f"上邊界線: {boundary_line_top:.1%} (Y={top_line_y}px)\n"
                            detection_text_result += f"下邊界線: {boundary_line_bottom:.1%} (Y={bottom_line_y}px)\n"
                            detection_text_result += "------------------------------------\n"

                            if results and hasattr(results[0], 'boxes') and len(results[0].boxes) > 0:
                                # 在影像上繪製檢測框
                                if draw_custom_boxes is not None:
                                    processed_image = draw_custom_boxes(image_rgb.copy(), results)
                                else:
                                    processed_image = image_rgb.copy()
                                
                                # 繪製邊界線
                                processed_image = cv2.line(processed_image, (0, top_line_y), (image_width, top_line_y), (255, 255, 0), 3)  # 黃色上線
                                processed_image = cv2.line(processed_image, (0, bottom_line_y), (image_width, bottom_line_y), (0, 255, 255), 3)  # 青色下線

                                # 準備文字輸出結果
                                detection_text_result += f"檢測到 {all_boxes_count} 個物件, 觸碰邊界線: {len(filtered_boxes)} 個:\n"
                                for i, box in enumerate(results[0].boxes):
                                    class_id = int(box.cls.item())
                                    conf = box.conf.item()
                                    # 獲取邊界框座標
                                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                                    touches_line = check_box_touches_boundary_lines(y1, y2, image_height)
                                    status = "✓ 觸線" if touches_line else "✗ 未觸線"
                                    detection_text_result += (
                                        f"  - 物件 {i+1}: Class ID={class_id}, "
                                        f"信心度={conf:.3f}, "
                                        f"位置=({x1:.0f},{y1:.0f})-({x2:.0f},{y2:.0f}) [{status}]\n"
                                    )
                            else:
                                processed_image = image_rgb.copy()
                                # 即使沒有檢測結果，也繪製邊界線
                                processed_image = cv2.line(processed_image, (0, top_line_y), (image_width, top_line_y), (255, 255, 0), 3)
                                processed_image = cv2.line(processed_image, (0, bottom_line_y), (image_width, bottom_line_y), (0, 255, 255), 3)
                                detection_text_result += "未檢測到任何物件。\n"

                            # 發送處理後的影像信號（帶辨識框和邊界線的）
                            if hasattr(signals, 'processed_image_ready'):
                                signals.processed_image_ready.emit(processed_image)

                            # 發送辨識結果文字信號
                            if hasattr(signals, 'detection_results_ready'):
                                signals.detection_results_ready.emit(detection_text_result)

                        except Exception as e:
                            print(f"AI Detection error: {e}")
                            if hasattr(signals, 'detection_results_ready'):
                                error_text = f"Frame: {self.st_frame_info.nFrameNum}\n"
                                error_text += f"AI 辨識時發生錯誤: {str(e)}\n"
                                signals.detection_results_ready.emit(error_text)
                    
                    else:
                        # ========================================
                        # AI 模型未載入時的處理
                        # ========================================
                        # 僅發送原始影像
                        if hasattr(signals, 'original_image_ready'):
                            # 翻轉後發送 RGB 格式
                            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
                            image_rgb = cv2.flip(image_rgb, 1)
                            signals.original_image_ready.emit(image_rgb)
                        
                        if hasattr(signals, 'detection_results_ready'):
                            no_ai_text = f"Frame: {self.st_frame_info.nFrameNum}\n"
                            no_ai_text += "AI 模型未載入。\n"
                            signals.detection_results_ready.emit(no_ai_text)
    
                else:
                    # ========================================
                    # 獲取圖像失敗的處理
                    # ========================================
                    print(f"Get frame failed, ret = {To_hex_str(ret)}")
    
                    if ret == MV_E_NODATA:
                        print("No data available")
                    elif ret == MV_E_TIMEOUT:
                        print("Get frame timeout")
                    else:
                        print(f"Unknown error: {ret}")
    
                    time.sleep(0.01)  # 短暫休眠避免 CPU 佔用過高
                    continue
                
            except Exception as e:
                print(f"Work thread exception: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(0.01)
                continue
            
        # ========================================
        # 線程結束清理
        # ========================================
        print("Work thread finished.")
        if hasattr(self, 'buf_grab_image') and self.buf_grab_image is not None:
            del self.buf_grab_image
        if hasattr(self, 'buf_save_image') and self.buf_save_image is not None:
            del self.buf_save_image

    def Save_jpg(self):
        """保存 JPG 圖像"""
        if self.buf_save_image is None:
            return

        # 獲取緩存鎖
        self.buf_lock.acquire()

        file_path = str(self.st_frame_info.nFrameNum) + ".jpg"

        stSaveParam = MV_SAVE_IMG_TO_FILE_PARAM()
        stSaveParam.enPixelType = self.st_frame_info.enPixelType
        stSaveParam.nWidth = self.st_frame_info.nWidth
        stSaveParam.nHeight = self.st_frame_info.nHeight
        stSaveParam.nDataLen = self.st_frame_info.nFrameLen
        stSaveParam.pData = cast(self.buf_save_image, POINTER(c_ubyte))
        stSaveParam.enImageType = MV_Image_Jpeg
        stSaveParam.nQuality = 80
        stSaveParam.pImagePath = file_path.encode('ascii')
        stSaveParam.iMethodValue = 2
        ret = self.obj_cam.MV_CC_SaveImageToFile(stSaveParam)

        self.buf_lock.release()
        return ret

    def Save_Bmp(self):
        """保存 BMP 圖像"""
        if self.buf_save_image is None:
            return

        # 獲取緩存鎖
        self.buf_lock.acquire()

        file_path = str(self.st_frame_info.nFrameNum) + ".bmp"

        stSaveParam = MV_SAVE_IMG_TO_FILE_PARAM()
        stSaveParam.enPixelType = self.st_frame_info.enPixelType
        stSaveParam.nWidth = self.st_frame_info.nWidth
        stSaveParam.nHeight = self.st_frame_info.nHeight
        stSaveParam.nDataLen = self.st_frame_info.nFrameLen
        stSaveParam.pData = cast(self.buf_save_image, POINTER(c_ubyte))
        stSaveParam.enImageType = MV_Image_Bmp
        stSaveParam.nQuality = 8
        stSaveParam.pImagePath = file_path.encode('ascii')
        stSaveParam.iMethodValue = 2
        ret = self.obj_cam.MV_CC_SaveImageToFile(stSaveParam)

        self.buf_lock.release()
        return ret