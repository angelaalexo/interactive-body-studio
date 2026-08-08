const viewer=document.getElementById('bodyViewer');
const femaleButton=document.getElementById('femaleButton');
const maleButton=document.getElementById('maleButton');
const customButton=document.getElementById('customButton');
const reloadCustomButton=document.getElementById('reloadCustomButton');
const resetViewButton=document.getElementById('resetViewButton');
const loadingMessage=document.getElementById('loadingMessage');

const ui={
 title:document.getElementById('characterTitle'),
 description:document.getElementById('characterDescription'),
 height:document.getElementById('heightValue'),
 weight:document.getElementById('weightValue'),
 chest:document.getElementById('chestValue'),
 waist:document.getElementById('waistValue'),
 hips:document.getElementById('hipsValue'),
 thighs:document.getElementById('thighsValue'),
 topName:document.getElementById('topName'),
 topSize:document.getElementById('topSize'),
 topScore:document.getElementById('topScore'),
 topBar:document.getElementById('topScoreBar'),
 bottomName:document.getElementById('bottomName'),
 bottomSize:document.getElementById('bottomSize'),
 bottomScore:document.getElementById('bottomScore'),
 bottomBar:document.getElementById('bottomScoreBar'),
 skinLabel:document.getElementById('skinLabel')
};

const defaults={
 female:{
  src:'models/female_model.glb',
  title:'Female reference model',
  description:'Default female body with a selected fitted outfit.',
  height:160,weight:57,chest:86,waist:67,hips:94,thighs:54,
  skin:'LIGHT',
  top:{label:'Sleeveless Shirt',size:'M',score:98},
  bottom:{label:'Female Skirt',size:'M',score:97}
 },
 male:{
  src:'models/male_model.glb',
  title:'Male reference model',
  description:'Default male body with a selected fitted outfit.',
  height:180,weight:78,chest:102,waist:83,hips:98,thighs:59,
  skin:'LIGHT',
  top:{label:'Male T-Shirt',size:'M',score:98},
  bottom:{label:'Male Shorts',size:'M',score:98}
 }
};

function fmt(value,unit){
 if(value===undefined||value===null||value==='') return '—';
 return `${value} ${unit}`;
}

function updateSkin(skin){
 document.querySelectorAll('.skin-swatch').forEach(x=>x.classList.remove('selected'));
 const map={FAIR:'.fair',LIGHT:'.light',TAN:'.tan',DARK:'.dark',BLACK:'.black'};
 const el=document.querySelector(map[skin]||'.light');
 if(el) el.classList.add('selected');
 ui.skinLabel.textContent=(skin||'LIGHT').toLowerCase().replace(/^./,c=>c.toUpperCase());
}

function updateDashboard(data){
 ui.title.textContent=data.title||'My Created Model';
 ui.description.textContent=data.description||'Personalized character exported from Blender.';
 ui.height.textContent=fmt(data.height,'cm');
 ui.weight.textContent=fmt(data.weight,'kg');
 ui.chest.textContent=fmt(data.chest,'cm');
 ui.waist.textContent=fmt(data.waist,'cm');
 ui.hips.textContent=fmt(data.hips,'cm');
 ui.thighs.textContent=fmt(data.thighs,'cm');

 const top=data.top||{};
 const bottom=data.bottom||{};

 ui.topName.textContent=top.label||'None';
 ui.topSize.textContent=top.size||'—';
 ui.topScore.textContent=top.score!==undefined?`${top.score}%`:'—';
 ui.topBar.style.width=top.score!==undefined?`${top.score}%`:'0%';

 ui.bottomName.textContent=bottom.label||'None';
 ui.bottomSize.textContent=bottom.size||'—';
 ui.bottomScore.textContent=bottom.score!==undefined?`${bottom.score}%`:'—';
 ui.bottomBar.style.width=bottom.score!==undefined?`${bottom.score}%`:'0%';

 updateSkin(data.skin);
}

function setActive(type){
 femaleButton.classList.toggle('active',type==='female');
 maleButton.classList.toggle('active',type==='male');
 customButton.classList.toggle('active',type==='custom');
}

function showDefault(type){
 const data=defaults[type];
 loadingMessage.hidden=false;
 loadingMessage.textContent='Loading 3D model…';
 viewer.src=`${data.src}?v=${Date.now()}`;
 updateDashboard(data);
 setActive(type);
}

async function loadCustom(){
 loadingMessage.hidden=false;
 loadingMessage.textContent='Loading created model…';

 try{
  const response=await fetch(`models/current_character.json?v=${Date.now()}`,{cache:'no-store'});
  if(!response.ok) throw new Error('JSON not found');
  const json=await response.json();

  const data={
   ...json,
   title:'My Created Model',
   description:'Personalized character exported directly from Blender.'
  };

  viewer.src=`models/current_character.glb?v=${Date.now()}`;
  updateDashboard(data);
  setActive('custom');
 }catch(error){
  loadingMessage.hidden=false;
  loadingMessage.textContent='Export a character from Blender first.';
 }
}

femaleButton.onclick=()=>showDefault('female');
maleButton.onclick=()=>showDefault('male');
customButton.onclick=loadCustom;
reloadCustomButton.onclick=loadCustom;

resetViewButton.onclick=()=>{
 viewer.cameraOrbit='0deg 82deg 3m';
 viewer.fieldOfView='30deg';
 viewer.jumpCameraToGoal();
};

viewer.addEventListener('load',()=>loadingMessage.hidden=true);
viewer.addEventListener('error',()=>{
 loadingMessage.hidden=false;
 loadingMessage.textContent='Model could not load. Check the files in the models folder.';
});
