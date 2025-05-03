1. api versioning
2. r2 instead of s3
3. use whisper-timestamped instead of openai-whisper
4. datetime.utcnow is deprected, modify it, also keep some project instruction for next projects. 
5. since we have to create a factual script, we might need to use gemini flash with search grounding. 
6. fetch images based on the script generated and then use accordingly. 
7. instead of serp, use google's search to get the images. 
8. lets do 720p videos and compress them. i think we have to use ffmpeg and not moviepy
9. upload audio, images, videos in background asynchrounously. 
10. understand r2 upload and its config properly. 
11. structure the folders properly in cloudflare.
12. use groq whisper to get the transcriptions. 
<!-- 13. fix thumbnail image upload issues.  -->
14. get images based on the transcript section, so we put relevant images for that part of the video. 

venkat
ZvqBLJP5zionOzUs

mitch, indigo, gail, Deedee, Cheyenne, Celeste, Atlas, Arista


Encode Manually: Use software like FFmpeg to convert your source video into multiple quality levels and segment them for HLS/DASH before uploading. This requires technical knowledge.
Upload All Files: Upload the manifest file(s) and all the small video segment files to your R2 bucket.
Implement Player: Integrate and configure a JavaScript video player on your website to point to the HLS/DASH manifest URL in R2.


### audio is not merging to the video, I can't listen to the audio, what is the issue and how to fix it?
The root cause was that by default ffmpeg only pulls streams from the first input (your image concat) and ignores the second (audio) unless you explicitly map them. I’ve added:
- “-map 0:v” (video from the concat input)
- “-map 1:a” (audio from your audio file)