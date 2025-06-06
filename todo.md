<!-- 1. api versioning -->
<!-- 2. r2 instead of s3 -->
<!-- 3. use whisper-timestamped instead of openai-whisper -->
<!-- 4. datetime.utcnow is deprected, modify it, also keep some project instruction for next projects.  -->
<!-- 5. since we have to create a factual script, we might need to use gemini flash with search grounding. -->
9. upload audio, images, videos in background asynchrounously.
10. understand r2 upload and its config properly.
11. structure the folders properly in cloudflare.
<!-- 12. use groq whisper to get the transcriptions.  -->
<!-- 13. fix thumbnail image upload issues.  -->
13. production r2 url so we can enable caching.
14. scroll means go to next reel, mobile responsive
15. play pause button.
<!-- 18. when we click on unmute button on a reel in explore page we are essentially opening a new page right, lets dont do that instead simply unmute and play the audio.  -->
<!-- 19. we are using groq, gemini clients many where on the code base, do we create once and use it everywhere, would it improve any perf? -->
16. store times taken for different stages.
17. optimze the backend. [link](https://t3.chat/chat/3fe35d86-e144-4081-b9da-9cec19e7c076)
18. no need for api/routes. lets just have routes folder.
19. using async clients, requests wherever possible for network requests. research if we can use async in other areas of the application.
20. put models names in a proper way, remove them from env.
21. video composing part we can do it in colab or laptop, we can put that in pending and do all that composing and upload it to r2 and update db from there. this would enables us to build higher quality videos.
28. we have to do different process parallely, since it is just network calls, that would be better if we can do them parallely.
32. we can use other services, but lets stick to gemini wherever possible, because if in case we get more users, everything will fail, if used, we need to have a lot of fall backs
33. we have to generate a lot of videos, we need to have a colab in which it processes the videos one by one, we can then send a notification to the user about it.
34. Dont use llama 3.3 70b anywhere, use llama 4 maverick.
35. login with differnt social platform like youtube so as to allow the users to post the content from anywhere.
37. implement rate limiting
38. implement best security practices. [chatgpt](https://chatgpt.com/c/68093130-6d70-800a-8658-ba6c5a5e063d)
39. write tests
40. we have to show script first, let the user's edit script. if all ok, then we can proceed with video generation. we can even fetch images and let user decide which to keep and which to remove.
41. sign in with mock account, which has a youtube channel logged in so users can test them.
- which parts of the code we can do with async more, to get optimal performance. 

--------------------------------------------------------------------------------------------------------------
Manim
- new 2.5 pro for manim code gen and run that to get the videos.
- for manim, to run llm generated code, use something like manim.
- with manim video gen, we have to give options whether to produce audio or not. we have to run this manim llm code in a sandbox environment.
- for manim code generation, we have to give proper working examples.
--------------------------------------------------------------------------------------------------------------


--------------------------------------------------------------------------------------------------------------
You’ve dealt with queues, sockets, streaming, or real-time infra. Or want to.
You’ve worked on systems where latency, uptime, and scale actually matter
--------------------------------------------------------------------------------------------------------------

pinterest image api? apify
what is the best way to aggregate or get images. 


--------------------------------------------------------------------------------------------------------------
SCENE
- lets have a seperate workflow for the scenes without effecting the existing ones. we can give two options in the api. 
- json2video
- we can generate scenes, script for that scene, image prompt for this scene
- so if we have an video editor online, we can give them option to change image or script for a particular scene without affecting eveything.
{
    title: "",
    scenes: [
        {
            scene_no: 1,
            script : "",
            image_video_search_query: "", most suitable based on the script,
            ai_image_prompt : "",
        }
    ]
}
we will let the models decide what to return. we don't need both image_video_search_query, ai_image_prompt.
for human people, celebreties, lets ask it for image_video_search_query. lets say if the script says something like bharath ratna, we have to try to get an image with bharat ratna and the person taking it. 
dialogue or narration : for stories we want narration.

- handle script editing, image changing scene by scene.
- when script and image is ready we can proceed with audio, video generation.
- we have to handle multiple video generations for a script, show all of them relevant to that script. 
--------------------------------------------------------------------------------------------------------------

--------------------------------------------------------------------------------------------------------------
Images and Videos:
- lets try to fetch high quality images. 
- properly integrate serp api, also store title and other meta and also do this with brave image search api. wuse the info to select which images to use for a scene
- we can use the metadata from image search results to properly set image for a scene.
- we are capturing thumbnail image with cv2, lets take the first image direclty as the thumbnail. no need for this computation. 
- instead of serp, use google's search to get the images. fall back to serp. 
- compress images, videos to appropriate quality.
- if watermark is present dont use it.
- do contextual images properly.
- lets do 480p videos only.
- lets try to fetch, use images without watermark.
- for ai generated images, we have to generate a lot of details so that images in all scenes will have same style etc to make the viewers believe we made an engaging story.
--------------------------------------------------------------------------------------------------------------

--------------------------------------------------------------------------------------------------------------
Audio and Sub: 
- use characters, timestamps from eleven labs audio gen api request. 
- we have to store audio duration, other meta data which can be used in compose_video. so there we dont have to run ffmpeg command to know the duration of the audio file.
- multiple language support. eleven labs dubbing api to make videos in multiple languages.
- SSML
- subtitle style, with coloring to the word being spoke dynamic styles and nice font.
- eleven labs also returns characters for second or something like that, I have to use it. but other voice providers may not return that so we have to handle this carefully.
- we can also add some background audio's or sound effects with eleven labs api.
- may use smallest.ai, sarvam bulbul v2
--------------------------------------------------------------------------------------------------------------

--------------------------------------------------------------------------------------------------------------
SCRIPT GENERATION
- Automatic model selection: different model for different use cases.
    1. use perplexity or gemini with search grounding for news, if we need to get latest info lets say for cricketers if we need their latest achievements etc. 
    2. if we need to generate a story simple one, lets use fast groq model or model which handles.
    3. for manim code gen, we have to use 2.5 pro as it is the best code gen model we have. 
    4. for 1,2 if we need complex scenes we need to use a bigger model for better results.

--------------------------------------------------------------------------------------------------------------





- We need to add video presets, fast, very fast across quality and resolution and fps so we might get video encoding faster.




- FFMPEG, ultrafast means low compression. 


- remove all the temp files created in the process. 


- i think we can do some processing asynchronously and parallely, like audio gen.
- we have to make this modular in such a way that we could do things parallely since all we do is make api calls, lets just do them parallely. 


google custom search api key : AIzaSyBMyiE8ybdPwyKNqj-6sdshkZOtRdeoxXE
<script async src="https://cse.google.com/cse.js?cx=c4255d4dc04524bf5">
</script>
<div class="gcse-search"></div>
serach engine id : c4255d4dc04524bf5



unreel speech : https://unrealspeech.com/pricing
250K characters
6 hours of audio


playai : https://play.ai/
30 minutes of speech credits
1 instant voice clone
3 private playnotes
1 concurrent playnote
1 concurrent text to speech generation
1 private agent
1 concurrent conversation with agent


- if we get many requests in the server, we have to do them one by one. like lets do a queue. mention that there are certain generations need to be done before this generation could be done. use CELERY + REDIS
- if we have lots of videos, lets not load all of them in the frontend
- in video composing as well, we have to include steps so that we can give more granular steps. 


Race Conditions on tempfile.gettempdir()
All generated files are placed in a shared temp dir with generic names (image_{i}_..., effect_segment_{i}.mp4), which can conflict across parallel runs.




CHALLENGES
out of memory in the cloud platform becuause of not removing unused things and it went out of memory. 
we were writing clips to the disk but this process is slow. we can do a ram only pipeline for getting all the clips and merging them but we have to take care of ram resources properly. 



• Replace “opencv-python” with “opencv-python-headless” (50 MB vs 200 MB).

- we dont need many clients right, if possible lets do with requests library.

- proper error handling, like what is the error message at which step it happened.
- hanlde fallbacks properly, check for subtitle generator.
- use a langchain/langraph to this app to make it better. 


- 


https://www.inngest.com/platform?ref=nav
https://modal.com/use-cases/job-queues

AI podcast clipper:
https://github.com/Andreaswt/ai-podcast-clipper-saas
https://www.youtube.com/watch?v=PeFZcvWucoU&lc=UgygPH-I4OnPzFLV1fZ4AaABAg
