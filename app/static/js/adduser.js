document.addEventListener("DOMContentLoaded",function(){

const form = document.getElementById("addUserForm");

form.addEventListener("submit",function(e){

const password = document.getElementById("passwordField").value;

if(password.length < 6){
alert("Password must be at least 6 characters");
e.preventDefault();
}

});

});