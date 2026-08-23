async function sendMessage(){
console.log("Send button clicked");
    let input=document.getElementById("user-input");

    let message=input.value;

    if(message=="") return;

    let chat=document.getElementById("chat-box");

    chat.innerHTML += "<p class='user'><b>You:</b> "+message+"</p>";

    let response=await fetch("/chat",{
        method:"POST",
        headers:{
            "Content-Type":"application/json"
        },
        body:JSON.stringify({
            message:message
        })
    });

    let data=await response.json();

    chat.innerHTML += "<p class='bot'><b>Bot:</b> "+data.response+"</p>";

    input.value="";

    chat.scrollTop=chat.scrollHeight;

}

document.getElementById("user-input").addEventListener("keypress", function(event) {

    if (event.key === "Enter") {
        event.preventDefault();
        sendMessage();
    }

});