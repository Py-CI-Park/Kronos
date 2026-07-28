/* Generated from docs/schemas/kronos_rl_api_v2.schema.json; schema-sha256: 2ab539e23ad4df9ea7c48428068ae0859d57acdeb1fbed28e739f23349cdc004; ajv@8.20.0 + ajv-formats@3.0.1. Do not edit. */
/* Ajv2020 options: {"strict":true,"strictSchema":true,"strictTypes":true,"strictTuples":true,"allErrors":true,"validateFormats":true,"unicodeRegExp":true,"ownProperties":true,"coerceTypes":false,"useDefaults":false,"removeAdditional":false,"allowUnionTypes":false,"code":{"esm":true,"source":true,"lines":true}}; formats: date-time,date,uuid. */
// @ts-nocheck
"use strict";
export const validateRunsRoot = validate74;
const schema32 = {"type":"object","additionalProperties":false,"required":["route_id","source","list","locks"],"properties":{"route_id":{"const":"RUNS"},"source":{"$ref":"#/$defs/source"},"locks":{"$ref":"#/$defs/locks"},"list":{"type":"object","additionalProperties":false,"required":["items","next_cursor"],"properties":{"items":{"type":"array","maxItems":100,"items":{"$ref":"#/$defs/run"}},"next_cursor":{"anyOf":[{"$ref":"#/$defs/cursor"},{"type":"null"}]}}}}};
const schema36 = {"type":"object","additionalProperties":false,"required":["promotion_allowed","model_build_allowed","paper_forward_allowed","live_broker_order_allowed","profitability_claim_allowed","go_summary_allowed"],"properties":{"promotion_allowed":{"const":false},"model_build_allowed":{"const":false},"paper_forward_allowed":{"const":false},"live_broker_order_allowed":{"const":false},"profitability_claim_allowed":{"const":false},"go_summary_allowed":{"const":false}}};
const schema48 = {"type":"string","pattern":"^[A-Za-z0-9_-]+$","minLength":16,"maxLength":2048};
const func0 = Object.prototype.hasOwnProperty;
import ucs2length from "ajv/dist/runtime/ucs2length.js";
const func114 = ucs2length;
const schema33 = {"type":"object","additionalProperties":false,"required":["source_sha256","generated_at"],"properties":{"source_sha256":{"$ref":"#/$defs/sha256"},"generated_at":{"$ref":"#/$defs/utc"}}};
const schema34 = {"type":"string","pattern":"^[0-9a-f]{64}$"};
const schema35 = {"type":"string","pattern":"^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$","format":"date-time"};
const pattern4 = new RegExp("^[0-9a-f]{64}$", "u");
const pattern5 = new RegExp("^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$", "u");
import formats from "ajv-formats/dist/formats.js";
const formats0 = formats.fullFormats["date-time"];

function validate22(data, {instancePath="", parentData, parentDataProperty, rootData=data, dynamicAnchors={}}={}){
let vErrors = null;
let errors = 0;
const evaluated0 = validate22.evaluated;
if(evaluated0.dynamicProps){
evaluated0.props = undefined;
}
if(evaluated0.dynamicItems){
evaluated0.items = undefined;
}
if(data && typeof data == "object" && !Array.isArray(data)){
if((data.source_sha256 === undefined) || (!(func0.call(data, "source_sha256")))){
const err0 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "source_sha256"},message:"must have required property '"+"source_sha256"+"'"};
if(vErrors === null){
vErrors = [err0];
}
else {
vErrors.push(err0);
}
errors++;
}
if((data.generated_at === undefined) || (!(func0.call(data, "generated_at")))){
const err1 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "generated_at"},message:"must have required property '"+"generated_at"+"'"};
if(vErrors === null){
vErrors = [err1];
}
else {
vErrors.push(err1);
}
errors++;
}
for(const key0 of Object.keys(data)){
if(!((key0 === "source_sha256") || (key0 === "generated_at"))){
const err2 = {instancePath,schemaPath:"#/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key0},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err2];
}
else {
vErrors.push(err2);
}
errors++;
}
}
if(data.source_sha256 !== undefined && func0.call(data, "source_sha256")){
let data0 = data.source_sha256;
if(typeof data0 === "string"){
if(!pattern4.test(data0)){
const err3 = {instancePath:instancePath+"/source_sha256",schemaPath:"#/$defs/sha256/pattern",keyword:"pattern",params:{pattern: "^[0-9a-f]{64}$"},message:"must match pattern \""+"^[0-9a-f]{64}$"+"\""};
if(vErrors === null){
vErrors = [err3];
}
else {
vErrors.push(err3);
}
errors++;
}
}
else {
const err4 = {instancePath:instancePath+"/source_sha256",schemaPath:"#/$defs/sha256/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err4];
}
else {
vErrors.push(err4);
}
errors++;
}
}
if(data.generated_at !== undefined && func0.call(data, "generated_at")){
let data1 = data.generated_at;
if(typeof data1 === "string"){
if(!pattern5.test(data1)){
const err5 = {instancePath:instancePath+"/generated_at",schemaPath:"#/$defs/utc/pattern",keyword:"pattern",params:{pattern: "^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"},message:"must match pattern \""+"^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"+"\""};
if(vErrors === null){
vErrors = [err5];
}
else {
vErrors.push(err5);
}
errors++;
}
if(!(formats0.validate(data1))){
const err6 = {instancePath:instancePath+"/generated_at",schemaPath:"#/$defs/utc/format",keyword:"format",params:{format: "date-time"},message:"must match format \""+"date-time"+"\""};
if(vErrors === null){
vErrors = [err6];
}
else {
vErrors.push(err6);
}
errors++;
}
}
else {
const err7 = {instancePath:instancePath+"/generated_at",schemaPath:"#/$defs/utc/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err7];
}
else {
vErrors.push(err7);
}
errors++;
}
}
}
else {
const err8 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err8];
}
else {
vErrors.push(err8);
}
errors++;
}
validate22.errors = vErrors;
return errors === 0;
}
validate22.evaluated = {"props":true,"dynamicProps":false,"dynamicItems":false};

const schema37 = {"type":"object","additionalProperties":false,"required":["run_id","state","source_sha256","created_at"],"properties":{"run_id":{"$ref":"#/$defs/runId"},"run_uid":{"$ref":"#/$defs/runId"},"run_revision":{"$ref":"#/$defs/runRevision"},"state":{"$ref":"#/$defs/runState"},"source_sha256":{"$ref":"#/$defs/sha256"},"created_at":{"$ref":"#/$defs/utc"}}};
const schema38 = {"type":"string","pattern":"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"};
const schema40 = {"type":"integer","minimum":1,"maximum":9007199254740991};
const pattern6 = new RegExp("^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$", "u");
const schema41 = {"type":"object","additionalProperties":false,"required":["status","progress","updated_at","started_at","finished_at"],"properties":{"status":{"enum":["QUEUED","RUNNING","SUCCEEDED","FAILED","CANCELLED"]},"progress":{"$ref":"#/$defs/progress"},"updated_at":{"$ref":"#/$defs/utc"},"started_at":{"anyOf":[{"$ref":"#/$defs/utc"},{"type":"null"}]},"finished_at":{"anyOf":[{"$ref":"#/$defs/utc"},{"type":"null"}]}}};
const schema42 = {"type":"object","additionalProperties":false,"required":["step","total_steps","percent"],"properties":{"step":{"type":"integer","minimum":0,"maximum":9007199254740991},"total_steps":{"type":"integer","minimum":1,"maximum":9007199254740991},"percent":{"type":"number","minimum":0,"maximum":100}}};

function validate25(data, {instancePath="", parentData, parentDataProperty, rootData=data, dynamicAnchors={}}={}){
let vErrors = null;
let errors = 0;
const evaluated0 = validate25.evaluated;
if(evaluated0.dynamicProps){
evaluated0.props = undefined;
}
if(evaluated0.dynamicItems){
evaluated0.items = undefined;
}
if(data && typeof data == "object" && !Array.isArray(data)){
if((data.status === undefined) || (!(func0.call(data, "status")))){
const err0 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "status"},message:"must have required property '"+"status"+"'"};
if(vErrors === null){
vErrors = [err0];
}
else {
vErrors.push(err0);
}
errors++;
}
if((data.progress === undefined) || (!(func0.call(data, "progress")))){
const err1 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "progress"},message:"must have required property '"+"progress"+"'"};
if(vErrors === null){
vErrors = [err1];
}
else {
vErrors.push(err1);
}
errors++;
}
if((data.updated_at === undefined) || (!(func0.call(data, "updated_at")))){
const err2 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "updated_at"},message:"must have required property '"+"updated_at"+"'"};
if(vErrors === null){
vErrors = [err2];
}
else {
vErrors.push(err2);
}
errors++;
}
if((data.started_at === undefined) || (!(func0.call(data, "started_at")))){
const err3 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "started_at"},message:"must have required property '"+"started_at"+"'"};
if(vErrors === null){
vErrors = [err3];
}
else {
vErrors.push(err3);
}
errors++;
}
if((data.finished_at === undefined) || (!(func0.call(data, "finished_at")))){
const err4 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "finished_at"},message:"must have required property '"+"finished_at"+"'"};
if(vErrors === null){
vErrors = [err4];
}
else {
vErrors.push(err4);
}
errors++;
}
for(const key0 of Object.keys(data)){
if(!(((((key0 === "status") || (key0 === "progress")) || (key0 === "updated_at")) || (key0 === "started_at")) || (key0 === "finished_at"))){
const err5 = {instancePath,schemaPath:"#/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key0},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err5];
}
else {
vErrors.push(err5);
}
errors++;
}
}
if(data.status !== undefined && func0.call(data, "status")){
let data0 = data.status;
if(!(((((data0 === "QUEUED") || (data0 === "RUNNING")) || (data0 === "SUCCEEDED")) || (data0 === "FAILED")) || (data0 === "CANCELLED"))){
const err6 = {instancePath:instancePath+"/status",schemaPath:"#/properties/status/enum",keyword:"enum",params:{allowedValues: schema41.properties.status.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err6];
}
else {
vErrors.push(err6);
}
errors++;
}
}
if(data.progress !== undefined && func0.call(data, "progress")){
let data1 = data.progress;
if(data1 && typeof data1 == "object" && !Array.isArray(data1)){
if((data1.step === undefined) || (!(func0.call(data1, "step")))){
const err7 = {instancePath:instancePath+"/progress",schemaPath:"#/$defs/progress/required",keyword:"required",params:{missingProperty: "step"},message:"must have required property '"+"step"+"'"};
if(vErrors === null){
vErrors = [err7];
}
else {
vErrors.push(err7);
}
errors++;
}
if((data1.total_steps === undefined) || (!(func0.call(data1, "total_steps")))){
const err8 = {instancePath:instancePath+"/progress",schemaPath:"#/$defs/progress/required",keyword:"required",params:{missingProperty: "total_steps"},message:"must have required property '"+"total_steps"+"'"};
if(vErrors === null){
vErrors = [err8];
}
else {
vErrors.push(err8);
}
errors++;
}
if((data1.percent === undefined) || (!(func0.call(data1, "percent")))){
const err9 = {instancePath:instancePath+"/progress",schemaPath:"#/$defs/progress/required",keyword:"required",params:{missingProperty: "percent"},message:"must have required property '"+"percent"+"'"};
if(vErrors === null){
vErrors = [err9];
}
else {
vErrors.push(err9);
}
errors++;
}
for(const key1 of Object.keys(data1)){
if(!(((key1 === "step") || (key1 === "total_steps")) || (key1 === "percent"))){
const err10 = {instancePath:instancePath+"/progress",schemaPath:"#/$defs/progress/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key1},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err10];
}
else {
vErrors.push(err10);
}
errors++;
}
}
if(data1.step !== undefined && func0.call(data1, "step")){
let data2 = data1.step;
if(!(((typeof data2 == "number") && (!(data2 % 1) && !isNaN(data2))) && (isFinite(data2)))){
const err11 = {instancePath:instancePath+"/progress/step",schemaPath:"#/$defs/progress/properties/step/type",keyword:"type",params:{type: "integer"},message:"must be integer"};
if(vErrors === null){
vErrors = [err11];
}
else {
vErrors.push(err11);
}
errors++;
}
if((typeof data2 == "number") && (isFinite(data2))){
if(data2 > 9007199254740991 || isNaN(data2)){
const err12 = {instancePath:instancePath+"/progress/step",schemaPath:"#/$defs/progress/properties/step/maximum",keyword:"maximum",params:{comparison: "<=", limit: 9007199254740991},message:"must be <= 9007199254740991"};
if(vErrors === null){
vErrors = [err12];
}
else {
vErrors.push(err12);
}
errors++;
}
if(data2 < 0 || isNaN(data2)){
const err13 = {instancePath:instancePath+"/progress/step",schemaPath:"#/$defs/progress/properties/step/minimum",keyword:"minimum",params:{comparison: ">=", limit: 0},message:"must be >= 0"};
if(vErrors === null){
vErrors = [err13];
}
else {
vErrors.push(err13);
}
errors++;
}
}
}
if(data1.total_steps !== undefined && func0.call(data1, "total_steps")){
let data3 = data1.total_steps;
if(!(((typeof data3 == "number") && (!(data3 % 1) && !isNaN(data3))) && (isFinite(data3)))){
const err14 = {instancePath:instancePath+"/progress/total_steps",schemaPath:"#/$defs/progress/properties/total_steps/type",keyword:"type",params:{type: "integer"},message:"must be integer"};
if(vErrors === null){
vErrors = [err14];
}
else {
vErrors.push(err14);
}
errors++;
}
if((typeof data3 == "number") && (isFinite(data3))){
if(data3 > 9007199254740991 || isNaN(data3)){
const err15 = {instancePath:instancePath+"/progress/total_steps",schemaPath:"#/$defs/progress/properties/total_steps/maximum",keyword:"maximum",params:{comparison: "<=", limit: 9007199254740991},message:"must be <= 9007199254740991"};
if(vErrors === null){
vErrors = [err15];
}
else {
vErrors.push(err15);
}
errors++;
}
if(data3 < 1 || isNaN(data3)){
const err16 = {instancePath:instancePath+"/progress/total_steps",schemaPath:"#/$defs/progress/properties/total_steps/minimum",keyword:"minimum",params:{comparison: ">=", limit: 1},message:"must be >= 1"};
if(vErrors === null){
vErrors = [err16];
}
else {
vErrors.push(err16);
}
errors++;
}
}
}
if(data1.percent !== undefined && func0.call(data1, "percent")){
let data4 = data1.percent;
if((typeof data4 == "number") && (isFinite(data4))){
if(data4 > 100 || isNaN(data4)){
const err17 = {instancePath:instancePath+"/progress/percent",schemaPath:"#/$defs/progress/properties/percent/maximum",keyword:"maximum",params:{comparison: "<=", limit: 100},message:"must be <= 100"};
if(vErrors === null){
vErrors = [err17];
}
else {
vErrors.push(err17);
}
errors++;
}
if(data4 < 0 || isNaN(data4)){
const err18 = {instancePath:instancePath+"/progress/percent",schemaPath:"#/$defs/progress/properties/percent/minimum",keyword:"minimum",params:{comparison: ">=", limit: 0},message:"must be >= 0"};
if(vErrors === null){
vErrors = [err18];
}
else {
vErrors.push(err18);
}
errors++;
}
}
else {
const err19 = {instancePath:instancePath+"/progress/percent",schemaPath:"#/$defs/progress/properties/percent/type",keyword:"type",params:{type: "number"},message:"must be number"};
if(vErrors === null){
vErrors = [err19];
}
else {
vErrors.push(err19);
}
errors++;
}
}
}
else {
const err20 = {instancePath:instancePath+"/progress",schemaPath:"#/$defs/progress/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err20];
}
else {
vErrors.push(err20);
}
errors++;
}
}
if(data.updated_at !== undefined && func0.call(data, "updated_at")){
let data5 = data.updated_at;
if(typeof data5 === "string"){
if(!pattern5.test(data5)){
const err21 = {instancePath:instancePath+"/updated_at",schemaPath:"#/$defs/utc/pattern",keyword:"pattern",params:{pattern: "^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"},message:"must match pattern \""+"^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"+"\""};
if(vErrors === null){
vErrors = [err21];
}
else {
vErrors.push(err21);
}
errors++;
}
if(!(formats0.validate(data5))){
const err22 = {instancePath:instancePath+"/updated_at",schemaPath:"#/$defs/utc/format",keyword:"format",params:{format: "date-time"},message:"must match format \""+"date-time"+"\""};
if(vErrors === null){
vErrors = [err22];
}
else {
vErrors.push(err22);
}
errors++;
}
}
else {
const err23 = {instancePath:instancePath+"/updated_at",schemaPath:"#/$defs/utc/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err23];
}
else {
vErrors.push(err23);
}
errors++;
}
}
if(data.started_at !== undefined && func0.call(data, "started_at")){
let data6 = data.started_at;
const _errs17 = errors;
let valid4 = false;
const _errs18 = errors;
if(typeof data6 === "string"){
if(!pattern5.test(data6)){
const err24 = {instancePath:instancePath+"/started_at",schemaPath:"#/$defs/utc/pattern",keyword:"pattern",params:{pattern: "^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"},message:"must match pattern \""+"^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"+"\""};
if(vErrors === null){
vErrors = [err24];
}
else {
vErrors.push(err24);
}
errors++;
}
if(!(formats0.validate(data6))){
const err25 = {instancePath:instancePath+"/started_at",schemaPath:"#/$defs/utc/format",keyword:"format",params:{format: "date-time"},message:"must match format \""+"date-time"+"\""};
if(vErrors === null){
vErrors = [err25];
}
else {
vErrors.push(err25);
}
errors++;
}
}
else {
const err26 = {instancePath:instancePath+"/started_at",schemaPath:"#/$defs/utc/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err26];
}
else {
vErrors.push(err26);
}
errors++;
}
var _valid0 = _errs18 === errors;
valid4 = valid4 || _valid0;
const _errs21 = errors;
if(data6 !== null){
const err27 = {instancePath:instancePath+"/started_at",schemaPath:"#/properties/started_at/anyOf/1/type",keyword:"type",params:{type: "null"},message:"must be null"};
if(vErrors === null){
vErrors = [err27];
}
else {
vErrors.push(err27);
}
errors++;
}
var _valid0 = _errs21 === errors;
valid4 = valid4 || _valid0;
if(!valid4){
const err28 = {instancePath:instancePath+"/started_at",schemaPath:"#/properties/started_at/anyOf",keyword:"anyOf",params:{},message:"must match a schema in anyOf"};
if(vErrors === null){
vErrors = [err28];
}
else {
vErrors.push(err28);
}
errors++;
}
else {
errors = _errs17;
if(vErrors !== null){
if(_errs17){
vErrors.length = _errs17;
}
else {
vErrors = null;
}
}
}
}
if(data.finished_at !== undefined && func0.call(data, "finished_at")){
let data7 = data.finished_at;
const _errs24 = errors;
let valid6 = false;
const _errs25 = errors;
if(typeof data7 === "string"){
if(!pattern5.test(data7)){
const err29 = {instancePath:instancePath+"/finished_at",schemaPath:"#/$defs/utc/pattern",keyword:"pattern",params:{pattern: "^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"},message:"must match pattern \""+"^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"+"\""};
if(vErrors === null){
vErrors = [err29];
}
else {
vErrors.push(err29);
}
errors++;
}
if(!(formats0.validate(data7))){
const err30 = {instancePath:instancePath+"/finished_at",schemaPath:"#/$defs/utc/format",keyword:"format",params:{format: "date-time"},message:"must match format \""+"date-time"+"\""};
if(vErrors === null){
vErrors = [err30];
}
else {
vErrors.push(err30);
}
errors++;
}
}
else {
const err31 = {instancePath:instancePath+"/finished_at",schemaPath:"#/$defs/utc/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err31];
}
else {
vErrors.push(err31);
}
errors++;
}
var _valid1 = _errs25 === errors;
valid6 = valid6 || _valid1;
const _errs28 = errors;
if(data7 !== null){
const err32 = {instancePath:instancePath+"/finished_at",schemaPath:"#/properties/finished_at/anyOf/1/type",keyword:"type",params:{type: "null"},message:"must be null"};
if(vErrors === null){
vErrors = [err32];
}
else {
vErrors.push(err32);
}
errors++;
}
var _valid1 = _errs28 === errors;
valid6 = valid6 || _valid1;
if(!valid6){
const err33 = {instancePath:instancePath+"/finished_at",schemaPath:"#/properties/finished_at/anyOf",keyword:"anyOf",params:{},message:"must match a schema in anyOf"};
if(vErrors === null){
vErrors = [err33];
}
else {
vErrors.push(err33);
}
errors++;
}
else {
errors = _errs24;
if(vErrors !== null){
if(_errs24){
vErrors.length = _errs24;
}
else {
vErrors = null;
}
}
}
}
}
else {
const err34 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err34];
}
else {
vErrors.push(err34);
}
errors++;
}
validate25.errors = vErrors;
return errors === 0;
}
validate25.evaluated = {"props":true,"dynamicProps":false,"dynamicItems":false};


function validate24(data, {instancePath="", parentData, parentDataProperty, rootData=data, dynamicAnchors={}}={}){
let vErrors = null;
let errors = 0;
const evaluated0 = validate24.evaluated;
if(evaluated0.dynamicProps){
evaluated0.props = undefined;
}
if(evaluated0.dynamicItems){
evaluated0.items = undefined;
}
if(data && typeof data == "object" && !Array.isArray(data)){
if((data.run_id === undefined) || (!(func0.call(data, "run_id")))){
const err0 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "run_id"},message:"must have required property '"+"run_id"+"'"};
if(vErrors === null){
vErrors = [err0];
}
else {
vErrors.push(err0);
}
errors++;
}
if((data.state === undefined) || (!(func0.call(data, "state")))){
const err1 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "state"},message:"must have required property '"+"state"+"'"};
if(vErrors === null){
vErrors = [err1];
}
else {
vErrors.push(err1);
}
errors++;
}
if((data.source_sha256 === undefined) || (!(func0.call(data, "source_sha256")))){
const err2 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "source_sha256"},message:"must have required property '"+"source_sha256"+"'"};
if(vErrors === null){
vErrors = [err2];
}
else {
vErrors.push(err2);
}
errors++;
}
if((data.created_at === undefined) || (!(func0.call(data, "created_at")))){
const err3 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "created_at"},message:"must have required property '"+"created_at"+"'"};
if(vErrors === null){
vErrors = [err3];
}
else {
vErrors.push(err3);
}
errors++;
}
for(const key0 of Object.keys(data)){
if(!((((((key0 === "run_id") || (key0 === "run_uid")) || (key0 === "run_revision")) || (key0 === "state")) || (key0 === "source_sha256")) || (key0 === "created_at"))){
const err4 = {instancePath,schemaPath:"#/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key0},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err4];
}
else {
vErrors.push(err4);
}
errors++;
}
}
if(data.run_id !== undefined && func0.call(data, "run_id")){
let data0 = data.run_id;
if(typeof data0 === "string"){
if(!pattern6.test(data0)){
const err5 = {instancePath:instancePath+"/run_id",schemaPath:"#/$defs/runId/pattern",keyword:"pattern",params:{pattern: "^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"},message:"must match pattern \""+"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"+"\""};
if(vErrors === null){
vErrors = [err5];
}
else {
vErrors.push(err5);
}
errors++;
}
}
else {
const err6 = {instancePath:instancePath+"/run_id",schemaPath:"#/$defs/runId/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err6];
}
else {
vErrors.push(err6);
}
errors++;
}
}
if(data.run_uid !== undefined && func0.call(data, "run_uid")){
let data1 = data.run_uid;
if(typeof data1 === "string"){
if(!pattern6.test(data1)){
const err7 = {instancePath:instancePath+"/run_uid",schemaPath:"#/$defs/runId/pattern",keyword:"pattern",params:{pattern: "^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"},message:"must match pattern \""+"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"+"\""};
if(vErrors === null){
vErrors = [err7];
}
else {
vErrors.push(err7);
}
errors++;
}
}
else {
const err8 = {instancePath:instancePath+"/run_uid",schemaPath:"#/$defs/runId/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err8];
}
else {
vErrors.push(err8);
}
errors++;
}
}
if(data.run_revision !== undefined && func0.call(data, "run_revision")){
let data2 = data.run_revision;
if(!(((typeof data2 == "number") && (!(data2 % 1) && !isNaN(data2))) && (isFinite(data2)))){
const err9 = {instancePath:instancePath+"/run_revision",schemaPath:"#/$defs/runRevision/type",keyword:"type",params:{type: "integer"},message:"must be integer"};
if(vErrors === null){
vErrors = [err9];
}
else {
vErrors.push(err9);
}
errors++;
}
if((typeof data2 == "number") && (isFinite(data2))){
if(data2 > 9007199254740991 || isNaN(data2)){
const err10 = {instancePath:instancePath+"/run_revision",schemaPath:"#/$defs/runRevision/maximum",keyword:"maximum",params:{comparison: "<=", limit: 9007199254740991},message:"must be <= 9007199254740991"};
if(vErrors === null){
vErrors = [err10];
}
else {
vErrors.push(err10);
}
errors++;
}
if(data2 < 1 || isNaN(data2)){
const err11 = {instancePath:instancePath+"/run_revision",schemaPath:"#/$defs/runRevision/minimum",keyword:"minimum",params:{comparison: ">=", limit: 1},message:"must be >= 1"};
if(vErrors === null){
vErrors = [err11];
}
else {
vErrors.push(err11);
}
errors++;
}
}
}
if(data.state !== undefined && func0.call(data, "state")){
if(!(validate25(data.state, {instancePath:instancePath+"/state",parentData:data,parentDataProperty:"state",rootData,dynamicAnchors}))){
vErrors = vErrors === null ? validate25.errors : vErrors.concat(validate25.errors);
errors = vErrors.length;
}
}
if(data.source_sha256 !== undefined && func0.call(data, "source_sha256")){
let data4 = data.source_sha256;
if(typeof data4 === "string"){
if(!pattern4.test(data4)){
const err12 = {instancePath:instancePath+"/source_sha256",schemaPath:"#/$defs/sha256/pattern",keyword:"pattern",params:{pattern: "^[0-9a-f]{64}$"},message:"must match pattern \""+"^[0-9a-f]{64}$"+"\""};
if(vErrors === null){
vErrors = [err12];
}
else {
vErrors.push(err12);
}
errors++;
}
}
else {
const err13 = {instancePath:instancePath+"/source_sha256",schemaPath:"#/$defs/sha256/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err13];
}
else {
vErrors.push(err13);
}
errors++;
}
}
if(data.created_at !== undefined && func0.call(data, "created_at")){
let data5 = data.created_at;
if(typeof data5 === "string"){
if(!pattern5.test(data5)){
const err14 = {instancePath:instancePath+"/created_at",schemaPath:"#/$defs/utc/pattern",keyword:"pattern",params:{pattern: "^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"},message:"must match pattern \""+"^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"+"\""};
if(vErrors === null){
vErrors = [err14];
}
else {
vErrors.push(err14);
}
errors++;
}
if(!(formats0.validate(data5))){
const err15 = {instancePath:instancePath+"/created_at",schemaPath:"#/$defs/utc/format",keyword:"format",params:{format: "date-time"},message:"must match format \""+"date-time"+"\""};
if(vErrors === null){
vErrors = [err15];
}
else {
vErrors.push(err15);
}
errors++;
}
}
else {
const err16 = {instancePath:instancePath+"/created_at",schemaPath:"#/$defs/utc/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err16];
}
else {
vErrors.push(err16);
}
errors++;
}
}
}
else {
const err17 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err17];
}
else {
vErrors.push(err17);
}
errors++;
}
validate24.errors = vErrors;
return errors === 0;
}
validate24.evaluated = {"props":true,"dynamicProps":false,"dynamicItems":false};

const pattern13 = new RegExp("^[A-Za-z0-9_-]+$", "u");

function validate74(data, {instancePath="", parentData, parentDataProperty, rootData=data, dynamicAnchors={}}={}){
let vErrors = null;
let errors = 0;
const evaluated0 = validate74.evaluated;
if(evaluated0.dynamicProps){
evaluated0.props = undefined;
}
if(evaluated0.dynamicItems){
evaluated0.items = undefined;
}
if(data && typeof data == "object" && !Array.isArray(data)){
if((data.route_id === undefined) || (!(func0.call(data, "route_id")))){
const err0 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "route_id"},message:"must have required property '"+"route_id"+"'"};
if(vErrors === null){
vErrors = [err0];
}
else {
vErrors.push(err0);
}
errors++;
}
if((data.source === undefined) || (!(func0.call(data, "source")))){
const err1 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "source"},message:"must have required property '"+"source"+"'"};
if(vErrors === null){
vErrors = [err1];
}
else {
vErrors.push(err1);
}
errors++;
}
if((data.list === undefined) || (!(func0.call(data, "list")))){
const err2 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "list"},message:"must have required property '"+"list"+"'"};
if(vErrors === null){
vErrors = [err2];
}
else {
vErrors.push(err2);
}
errors++;
}
if((data.locks === undefined) || (!(func0.call(data, "locks")))){
const err3 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "locks"},message:"must have required property '"+"locks"+"'"};
if(vErrors === null){
vErrors = [err3];
}
else {
vErrors.push(err3);
}
errors++;
}
for(const key0 of Object.keys(data)){
if(!((((key0 === "route_id") || (key0 === "source")) || (key0 === "locks")) || (key0 === "list"))){
const err4 = {instancePath,schemaPath:"#/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key0},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err4];
}
else {
vErrors.push(err4);
}
errors++;
}
}
if(data.route_id !== undefined && func0.call(data, "route_id")){
if("RUNS" !== data.route_id){
const err5 = {instancePath:instancePath+"/route_id",schemaPath:"#/properties/route_id/const",keyword:"const",params:{allowedValue: "RUNS"},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err5];
}
else {
vErrors.push(err5);
}
errors++;
}
}
if(data.source !== undefined && func0.call(data, "source")){
if(!(validate22(data.source, {instancePath:instancePath+"/source",parentData:data,parentDataProperty:"source",rootData,dynamicAnchors}))){
vErrors = vErrors === null ? validate22.errors : vErrors.concat(validate22.errors);
errors = vErrors.length;
}
}
if(data.locks !== undefined && func0.call(data, "locks")){
let data2 = data.locks;
if(data2 && typeof data2 == "object" && !Array.isArray(data2)){
if((data2.promotion_allowed === undefined) || (!(func0.call(data2, "promotion_allowed")))){
const err6 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "promotion_allowed"},message:"must have required property '"+"promotion_allowed"+"'"};
if(vErrors === null){
vErrors = [err6];
}
else {
vErrors.push(err6);
}
errors++;
}
if((data2.model_build_allowed === undefined) || (!(func0.call(data2, "model_build_allowed")))){
const err7 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "model_build_allowed"},message:"must have required property '"+"model_build_allowed"+"'"};
if(vErrors === null){
vErrors = [err7];
}
else {
vErrors.push(err7);
}
errors++;
}
if((data2.paper_forward_allowed === undefined) || (!(func0.call(data2, "paper_forward_allowed")))){
const err8 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "paper_forward_allowed"},message:"must have required property '"+"paper_forward_allowed"+"'"};
if(vErrors === null){
vErrors = [err8];
}
else {
vErrors.push(err8);
}
errors++;
}
if((data2.live_broker_order_allowed === undefined) || (!(func0.call(data2, "live_broker_order_allowed")))){
const err9 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "live_broker_order_allowed"},message:"must have required property '"+"live_broker_order_allowed"+"'"};
if(vErrors === null){
vErrors = [err9];
}
else {
vErrors.push(err9);
}
errors++;
}
if((data2.profitability_claim_allowed === undefined) || (!(func0.call(data2, "profitability_claim_allowed")))){
const err10 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "profitability_claim_allowed"},message:"must have required property '"+"profitability_claim_allowed"+"'"};
if(vErrors === null){
vErrors = [err10];
}
else {
vErrors.push(err10);
}
errors++;
}
if((data2.go_summary_allowed === undefined) || (!(func0.call(data2, "go_summary_allowed")))){
const err11 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "go_summary_allowed"},message:"must have required property '"+"go_summary_allowed"+"'"};
if(vErrors === null){
vErrors = [err11];
}
else {
vErrors.push(err11);
}
errors++;
}
for(const key1 of Object.keys(data2)){
if(!((((((key1 === "promotion_allowed") || (key1 === "model_build_allowed")) || (key1 === "paper_forward_allowed")) || (key1 === "live_broker_order_allowed")) || (key1 === "profitability_claim_allowed")) || (key1 === "go_summary_allowed"))){
const err12 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key1},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err12];
}
else {
vErrors.push(err12);
}
errors++;
}
}
if(data2.promotion_allowed !== undefined && func0.call(data2, "promotion_allowed")){
if(false !== data2.promotion_allowed){
const err13 = {instancePath:instancePath+"/locks/promotion_allowed",schemaPath:"#/$defs/locks/properties/promotion_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err13];
}
else {
vErrors.push(err13);
}
errors++;
}
}
if(data2.model_build_allowed !== undefined && func0.call(data2, "model_build_allowed")){
if(false !== data2.model_build_allowed){
const err14 = {instancePath:instancePath+"/locks/model_build_allowed",schemaPath:"#/$defs/locks/properties/model_build_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err14];
}
else {
vErrors.push(err14);
}
errors++;
}
}
if(data2.paper_forward_allowed !== undefined && func0.call(data2, "paper_forward_allowed")){
if(false !== data2.paper_forward_allowed){
const err15 = {instancePath:instancePath+"/locks/paper_forward_allowed",schemaPath:"#/$defs/locks/properties/paper_forward_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err15];
}
else {
vErrors.push(err15);
}
errors++;
}
}
if(data2.live_broker_order_allowed !== undefined && func0.call(data2, "live_broker_order_allowed")){
if(false !== data2.live_broker_order_allowed){
const err16 = {instancePath:instancePath+"/locks/live_broker_order_allowed",schemaPath:"#/$defs/locks/properties/live_broker_order_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err16];
}
else {
vErrors.push(err16);
}
errors++;
}
}
if(data2.profitability_claim_allowed !== undefined && func0.call(data2, "profitability_claim_allowed")){
if(false !== data2.profitability_claim_allowed){
const err17 = {instancePath:instancePath+"/locks/profitability_claim_allowed",schemaPath:"#/$defs/locks/properties/profitability_claim_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err17];
}
else {
vErrors.push(err17);
}
errors++;
}
}
if(data2.go_summary_allowed !== undefined && func0.call(data2, "go_summary_allowed")){
if(false !== data2.go_summary_allowed){
const err18 = {instancePath:instancePath+"/locks/go_summary_allowed",schemaPath:"#/$defs/locks/properties/go_summary_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err18];
}
else {
vErrors.push(err18);
}
errors++;
}
}
}
else {
const err19 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err19];
}
else {
vErrors.push(err19);
}
errors++;
}
}
if(data.list !== undefined && func0.call(data, "list")){
let data9 = data.list;
if(data9 && typeof data9 == "object" && !Array.isArray(data9)){
if((data9.items === undefined) || (!(func0.call(data9, "items")))){
const err20 = {instancePath:instancePath+"/list",schemaPath:"#/properties/list/required",keyword:"required",params:{missingProperty: "items"},message:"must have required property '"+"items"+"'"};
if(vErrors === null){
vErrors = [err20];
}
else {
vErrors.push(err20);
}
errors++;
}
if((data9.next_cursor === undefined) || (!(func0.call(data9, "next_cursor")))){
const err21 = {instancePath:instancePath+"/list",schemaPath:"#/properties/list/required",keyword:"required",params:{missingProperty: "next_cursor"},message:"must have required property '"+"next_cursor"+"'"};
if(vErrors === null){
vErrors = [err21];
}
else {
vErrors.push(err21);
}
errors++;
}
for(const key2 of Object.keys(data9)){
if(!((key2 === "items") || (key2 === "next_cursor"))){
const err22 = {instancePath:instancePath+"/list",schemaPath:"#/properties/list/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key2},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err22];
}
else {
vErrors.push(err22);
}
errors++;
}
}
if(data9.items !== undefined && func0.call(data9, "items")){
let data10 = data9.items;
if(Array.isArray(data10)){
if(data10.length > 100){
const err23 = {instancePath:instancePath+"/list/items",schemaPath:"#/properties/list/properties/items/maxItems",keyword:"maxItems",params:{limit: 100},message:"must NOT have more than 100 items"};
if(vErrors === null){
vErrors = [err23];
}
else {
vErrors.push(err23);
}
errors++;
}
const len0 = data10.length;
for(let i0=0; i0<len0; i0++){
if(!(validate24(data10[i0], {instancePath:instancePath+"/list/items/" + i0,parentData:data10,parentDataProperty:i0,rootData,dynamicAnchors}))){
vErrors = vErrors === null ? validate24.errors : vErrors.concat(validate24.errors);
errors = vErrors.length;
}
}
}
else {
const err24 = {instancePath:instancePath+"/list/items",schemaPath:"#/properties/list/properties/items/type",keyword:"type",params:{type: "array"},message:"must be array"};
if(vErrors === null){
vErrors = [err24];
}
else {
vErrors.push(err24);
}
errors++;
}
}
if(data9.next_cursor !== undefined && func0.call(data9, "next_cursor")){
let data12 = data9.next_cursor;
const _errs21 = errors;
let valid6 = false;
const _errs22 = errors;
if(typeof data12 === "string"){
if(func114(data12) > 2048){
const err25 = {instancePath:instancePath+"/list/next_cursor",schemaPath:"#/$defs/cursor/maxLength",keyword:"maxLength",params:{limit: 2048},message:"must NOT have more than 2048 characters"};
if(vErrors === null){
vErrors = [err25];
}
else {
vErrors.push(err25);
}
errors++;
}
if(func114(data12) < 16){
const err26 = {instancePath:instancePath+"/list/next_cursor",schemaPath:"#/$defs/cursor/minLength",keyword:"minLength",params:{limit: 16},message:"must NOT have fewer than 16 characters"};
if(vErrors === null){
vErrors = [err26];
}
else {
vErrors.push(err26);
}
errors++;
}
if(!pattern13.test(data12)){
const err27 = {instancePath:instancePath+"/list/next_cursor",schemaPath:"#/$defs/cursor/pattern",keyword:"pattern",params:{pattern: "^[A-Za-z0-9_-]+$"},message:"must match pattern \""+"^[A-Za-z0-9_-]+$"+"\""};
if(vErrors === null){
vErrors = [err27];
}
else {
vErrors.push(err27);
}
errors++;
}
}
else {
const err28 = {instancePath:instancePath+"/list/next_cursor",schemaPath:"#/$defs/cursor/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err28];
}
else {
vErrors.push(err28);
}
errors++;
}
var _valid0 = _errs22 === errors;
valid6 = valid6 || _valid0;
const _errs25 = errors;
if(data12 !== null){
const err29 = {instancePath:instancePath+"/list/next_cursor",schemaPath:"#/properties/list/properties/next_cursor/anyOf/1/type",keyword:"type",params:{type: "null"},message:"must be null"};
if(vErrors === null){
vErrors = [err29];
}
else {
vErrors.push(err29);
}
errors++;
}
var _valid0 = _errs25 === errors;
valid6 = valid6 || _valid0;
if(!valid6){
const err30 = {instancePath:instancePath+"/list/next_cursor",schemaPath:"#/properties/list/properties/next_cursor/anyOf",keyword:"anyOf",params:{},message:"must match a schema in anyOf"};
if(vErrors === null){
vErrors = [err30];
}
else {
vErrors.push(err30);
}
errors++;
}
else {
errors = _errs21;
if(vErrors !== null){
if(_errs21){
vErrors.length = _errs21;
}
else {
vErrors = null;
}
}
}
}
}
else {
const err31 = {instancePath:instancePath+"/list",schemaPath:"#/properties/list/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err31];
}
else {
vErrors.push(err31);
}
errors++;
}
}
}
else {
const err32 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err32];
}
else {
vErrors.push(err32);
}
errors++;
}
validate74.errors = vErrors;
return errors === 0;
}
validate74.evaluated = {"props":true,"dynamicProps":false,"dynamicItems":false};

export const validateRunDetailRoot = validate77;
const schema49 = {"type":"object","additionalProperties":false,"required":["route_id","source","run","locks"],"properties":{"route_id":{"const":"RUN_DETAIL"},"source":{"$ref":"#/$defs/source"},"run":{"$ref":"#/$defs/run"},"locks":{"$ref":"#/$defs/locks"}}};

function validate77(data, {instancePath="", parentData, parentDataProperty, rootData=data, dynamicAnchors={}}={}){
let vErrors = null;
let errors = 0;
const evaluated0 = validate77.evaluated;
if(evaluated0.dynamicProps){
evaluated0.props = undefined;
}
if(evaluated0.dynamicItems){
evaluated0.items = undefined;
}
if(data && typeof data == "object" && !Array.isArray(data)){
if((data.route_id === undefined) || (!(func0.call(data, "route_id")))){
const err0 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "route_id"},message:"must have required property '"+"route_id"+"'"};
if(vErrors === null){
vErrors = [err0];
}
else {
vErrors.push(err0);
}
errors++;
}
if((data.source === undefined) || (!(func0.call(data, "source")))){
const err1 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "source"},message:"must have required property '"+"source"+"'"};
if(vErrors === null){
vErrors = [err1];
}
else {
vErrors.push(err1);
}
errors++;
}
if((data.run === undefined) || (!(func0.call(data, "run")))){
const err2 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "run"},message:"must have required property '"+"run"+"'"};
if(vErrors === null){
vErrors = [err2];
}
else {
vErrors.push(err2);
}
errors++;
}
if((data.locks === undefined) || (!(func0.call(data, "locks")))){
const err3 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "locks"},message:"must have required property '"+"locks"+"'"};
if(vErrors === null){
vErrors = [err3];
}
else {
vErrors.push(err3);
}
errors++;
}
for(const key0 of Object.keys(data)){
if(!((((key0 === "route_id") || (key0 === "source")) || (key0 === "run")) || (key0 === "locks"))){
const err4 = {instancePath,schemaPath:"#/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key0},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err4];
}
else {
vErrors.push(err4);
}
errors++;
}
}
if(data.route_id !== undefined && func0.call(data, "route_id")){
if("RUN_DETAIL" !== data.route_id){
const err5 = {instancePath:instancePath+"/route_id",schemaPath:"#/properties/route_id/const",keyword:"const",params:{allowedValue: "RUN_DETAIL"},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err5];
}
else {
vErrors.push(err5);
}
errors++;
}
}
if(data.source !== undefined && func0.call(data, "source")){
if(!(validate22(data.source, {instancePath:instancePath+"/source",parentData:data,parentDataProperty:"source",rootData,dynamicAnchors}))){
vErrors = vErrors === null ? validate22.errors : vErrors.concat(validate22.errors);
errors = vErrors.length;
}
}
if(data.run !== undefined && func0.call(data, "run")){
if(!(validate24(data.run, {instancePath:instancePath+"/run",parentData:data,parentDataProperty:"run",rootData,dynamicAnchors}))){
vErrors = vErrors === null ? validate24.errors : vErrors.concat(validate24.errors);
errors = vErrors.length;
}
}
if(data.locks !== undefined && func0.call(data, "locks")){
let data3 = data.locks;
if(data3 && typeof data3 == "object" && !Array.isArray(data3)){
if((data3.promotion_allowed === undefined) || (!(func0.call(data3, "promotion_allowed")))){
const err6 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "promotion_allowed"},message:"must have required property '"+"promotion_allowed"+"'"};
if(vErrors === null){
vErrors = [err6];
}
else {
vErrors.push(err6);
}
errors++;
}
if((data3.model_build_allowed === undefined) || (!(func0.call(data3, "model_build_allowed")))){
const err7 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "model_build_allowed"},message:"must have required property '"+"model_build_allowed"+"'"};
if(vErrors === null){
vErrors = [err7];
}
else {
vErrors.push(err7);
}
errors++;
}
if((data3.paper_forward_allowed === undefined) || (!(func0.call(data3, "paper_forward_allowed")))){
const err8 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "paper_forward_allowed"},message:"must have required property '"+"paper_forward_allowed"+"'"};
if(vErrors === null){
vErrors = [err8];
}
else {
vErrors.push(err8);
}
errors++;
}
if((data3.live_broker_order_allowed === undefined) || (!(func0.call(data3, "live_broker_order_allowed")))){
const err9 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "live_broker_order_allowed"},message:"must have required property '"+"live_broker_order_allowed"+"'"};
if(vErrors === null){
vErrors = [err9];
}
else {
vErrors.push(err9);
}
errors++;
}
if((data3.profitability_claim_allowed === undefined) || (!(func0.call(data3, "profitability_claim_allowed")))){
const err10 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "profitability_claim_allowed"},message:"must have required property '"+"profitability_claim_allowed"+"'"};
if(vErrors === null){
vErrors = [err10];
}
else {
vErrors.push(err10);
}
errors++;
}
if((data3.go_summary_allowed === undefined) || (!(func0.call(data3, "go_summary_allowed")))){
const err11 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "go_summary_allowed"},message:"must have required property '"+"go_summary_allowed"+"'"};
if(vErrors === null){
vErrors = [err11];
}
else {
vErrors.push(err11);
}
errors++;
}
for(const key1 of Object.keys(data3)){
if(!((((((key1 === "promotion_allowed") || (key1 === "model_build_allowed")) || (key1 === "paper_forward_allowed")) || (key1 === "live_broker_order_allowed")) || (key1 === "profitability_claim_allowed")) || (key1 === "go_summary_allowed"))){
const err12 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key1},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err12];
}
else {
vErrors.push(err12);
}
errors++;
}
}
if(data3.promotion_allowed !== undefined && func0.call(data3, "promotion_allowed")){
if(false !== data3.promotion_allowed){
const err13 = {instancePath:instancePath+"/locks/promotion_allowed",schemaPath:"#/$defs/locks/properties/promotion_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err13];
}
else {
vErrors.push(err13);
}
errors++;
}
}
if(data3.model_build_allowed !== undefined && func0.call(data3, "model_build_allowed")){
if(false !== data3.model_build_allowed){
const err14 = {instancePath:instancePath+"/locks/model_build_allowed",schemaPath:"#/$defs/locks/properties/model_build_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err14];
}
else {
vErrors.push(err14);
}
errors++;
}
}
if(data3.paper_forward_allowed !== undefined && func0.call(data3, "paper_forward_allowed")){
if(false !== data3.paper_forward_allowed){
const err15 = {instancePath:instancePath+"/locks/paper_forward_allowed",schemaPath:"#/$defs/locks/properties/paper_forward_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err15];
}
else {
vErrors.push(err15);
}
errors++;
}
}
if(data3.live_broker_order_allowed !== undefined && func0.call(data3, "live_broker_order_allowed")){
if(false !== data3.live_broker_order_allowed){
const err16 = {instancePath:instancePath+"/locks/live_broker_order_allowed",schemaPath:"#/$defs/locks/properties/live_broker_order_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err16];
}
else {
vErrors.push(err16);
}
errors++;
}
}
if(data3.profitability_claim_allowed !== undefined && func0.call(data3, "profitability_claim_allowed")){
if(false !== data3.profitability_claim_allowed){
const err17 = {instancePath:instancePath+"/locks/profitability_claim_allowed",schemaPath:"#/$defs/locks/properties/profitability_claim_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err17];
}
else {
vErrors.push(err17);
}
errors++;
}
}
if(data3.go_summary_allowed !== undefined && func0.call(data3, "go_summary_allowed")){
if(false !== data3.go_summary_allowed){
const err18 = {instancePath:instancePath+"/locks/go_summary_allowed",schemaPath:"#/$defs/locks/properties/go_summary_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err18];
}
else {
vErrors.push(err18);
}
errors++;
}
}
}
else {
const err19 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err19];
}
else {
vErrors.push(err19);
}
errors++;
}
}
}
else {
const err20 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err20];
}
else {
vErrors.push(err20);
}
errors++;
}
validate77.errors = vErrors;
return errors === 0;
}
validate77.evaluated = {"props":true,"dynamicProps":false,"dynamicItems":false};

export const validateEventsRoot = validate80;
const schema51 = {"type":"object","additionalProperties":false,"required":["route_id","source","list","locks","run_id"],"properties":{"route_id":{"const":"EVENTS"},"source":{"$ref":"#/$defs/source"},"locks":{"$ref":"#/$defs/locks"},"list":{"type":"object","additionalProperties":false,"required":["items","next_cursor"],"properties":{"items":{"type":"array","maxItems":100,"items":{"$ref":"#/$defs/event"}},"next_cursor":{"anyOf":[{"$ref":"#/$defs/cursor"},{"type":"null"}]}}},"run_id":{"$ref":"#/$defs/runId"}}};
const schema53 = {"oneOf":[{"type":"object","additionalProperties":false,"required":["event_type","event_id","occurred_at","payload_sha256","progress"],"properties":{"event_type":{"const":"PROGRESS"},"event_id":{"type":"string","minLength":1},"occurred_at":{"$ref":"#/$defs/utc"},"payload_sha256":{"$ref":"#/$defs/sha256"},"progress":{"$ref":"#/$defs/progress"}}},{"type":"object","additionalProperties":false,"required":["event_type","event_id","occurred_at","payload_sha256","level","message"],"properties":{"event_type":{"const":"MESSAGE"},"event_id":{"type":"string","minLength":1},"occurred_at":{"$ref":"#/$defs/utc"},"payload_sha256":{"$ref":"#/$defs/sha256"},"level":{"enum":["DEBUG","INFO","WARNING","ERROR"]},"message":{"type":"string","minLength":1}}},{"type":"object","additionalProperties":false,"required":["event_type","event_id","occurred_at","payload_sha256","artifact_id"],"properties":{"event_type":{"const":"ARTIFACT"},"event_id":{"type":"string","minLength":1},"occurred_at":{"$ref":"#/$defs/utc"},"payload_sha256":{"$ref":"#/$defs/sha256"},"artifact_id":{"$ref":"#/$defs/artifactId"}}},{"type":"object","additionalProperties":false,"required":["event_type","event_id","occurred_at","payload_sha256","state"],"properties":{"event_type":{"const":"STATE"},"event_id":{"type":"string","minLength":1},"occurred_at":{"$ref":"#/$defs/utc"},"payload_sha256":{"$ref":"#/$defs/sha256"},"state":{"$ref":"#/$defs/runState"}}}]};
const schema61 = {"type":"string","pattern":"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"};
const pattern20 = new RegExp("^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$", "u");

function validate35(data, {instancePath="", parentData, parentDataProperty, rootData=data, dynamicAnchors={}}={}){
let vErrors = null;
let errors = 0;
const evaluated0 = validate35.evaluated;
if(evaluated0.dynamicProps){
evaluated0.props = undefined;
}
if(evaluated0.dynamicItems){
evaluated0.items = undefined;
}
const _errs0 = errors;
let valid0 = false;
let passing0 = null;
const _errs1 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
if((data.event_type === undefined) || (!(func0.call(data, "event_type")))){
const err0 = {instancePath,schemaPath:"#/oneOf/0/required",keyword:"required",params:{missingProperty: "event_type"},message:"must have required property '"+"event_type"+"'"};
if(vErrors === null){
vErrors = [err0];
}
else {
vErrors.push(err0);
}
errors++;
}
if((data.event_id === undefined) || (!(func0.call(data, "event_id")))){
const err1 = {instancePath,schemaPath:"#/oneOf/0/required",keyword:"required",params:{missingProperty: "event_id"},message:"must have required property '"+"event_id"+"'"};
if(vErrors === null){
vErrors = [err1];
}
else {
vErrors.push(err1);
}
errors++;
}
if((data.occurred_at === undefined) || (!(func0.call(data, "occurred_at")))){
const err2 = {instancePath,schemaPath:"#/oneOf/0/required",keyword:"required",params:{missingProperty: "occurred_at"},message:"must have required property '"+"occurred_at"+"'"};
if(vErrors === null){
vErrors = [err2];
}
else {
vErrors.push(err2);
}
errors++;
}
if((data.payload_sha256 === undefined) || (!(func0.call(data, "payload_sha256")))){
const err3 = {instancePath,schemaPath:"#/oneOf/0/required",keyword:"required",params:{missingProperty: "payload_sha256"},message:"must have required property '"+"payload_sha256"+"'"};
if(vErrors === null){
vErrors = [err3];
}
else {
vErrors.push(err3);
}
errors++;
}
if((data.progress === undefined) || (!(func0.call(data, "progress")))){
const err4 = {instancePath,schemaPath:"#/oneOf/0/required",keyword:"required",params:{missingProperty: "progress"},message:"must have required property '"+"progress"+"'"};
if(vErrors === null){
vErrors = [err4];
}
else {
vErrors.push(err4);
}
errors++;
}
for(const key0 of Object.keys(data)){
if(!(((((key0 === "event_type") || (key0 === "event_id")) || (key0 === "occurred_at")) || (key0 === "payload_sha256")) || (key0 === "progress"))){
const err5 = {instancePath,schemaPath:"#/oneOf/0/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key0},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err5];
}
else {
vErrors.push(err5);
}
errors++;
}
}
if(data.event_type !== undefined && func0.call(data, "event_type")){
if("PROGRESS" !== data.event_type){
const err6 = {instancePath:instancePath+"/event_type",schemaPath:"#/oneOf/0/properties/event_type/const",keyword:"const",params:{allowedValue: "PROGRESS"},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err6];
}
else {
vErrors.push(err6);
}
errors++;
}
}
if(data.event_id !== undefined && func0.call(data, "event_id")){
let data1 = data.event_id;
if(typeof data1 === "string"){
if(func114(data1) < 1){
const err7 = {instancePath:instancePath+"/event_id",schemaPath:"#/oneOf/0/properties/event_id/minLength",keyword:"minLength",params:{limit: 1},message:"must NOT have fewer than 1 characters"};
if(vErrors === null){
vErrors = [err7];
}
else {
vErrors.push(err7);
}
errors++;
}
}
else {
const err8 = {instancePath:instancePath+"/event_id",schemaPath:"#/oneOf/0/properties/event_id/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err8];
}
else {
vErrors.push(err8);
}
errors++;
}
}
if(data.occurred_at !== undefined && func0.call(data, "occurred_at")){
let data2 = data.occurred_at;
if(typeof data2 === "string"){
if(!pattern5.test(data2)){
const err9 = {instancePath:instancePath+"/occurred_at",schemaPath:"#/$defs/utc/pattern",keyword:"pattern",params:{pattern: "^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"},message:"must match pattern \""+"^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"+"\""};
if(vErrors === null){
vErrors = [err9];
}
else {
vErrors.push(err9);
}
errors++;
}
if(!(formats0.validate(data2))){
const err10 = {instancePath:instancePath+"/occurred_at",schemaPath:"#/$defs/utc/format",keyword:"format",params:{format: "date-time"},message:"must match format \""+"date-time"+"\""};
if(vErrors === null){
vErrors = [err10];
}
else {
vErrors.push(err10);
}
errors++;
}
}
else {
const err11 = {instancePath:instancePath+"/occurred_at",schemaPath:"#/$defs/utc/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err11];
}
else {
vErrors.push(err11);
}
errors++;
}
}
if(data.payload_sha256 !== undefined && func0.call(data, "payload_sha256")){
let data3 = data.payload_sha256;
if(typeof data3 === "string"){
if(!pattern4.test(data3)){
const err12 = {instancePath:instancePath+"/payload_sha256",schemaPath:"#/$defs/sha256/pattern",keyword:"pattern",params:{pattern: "^[0-9a-f]{64}$"},message:"must match pattern \""+"^[0-9a-f]{64}$"+"\""};
if(vErrors === null){
vErrors = [err12];
}
else {
vErrors.push(err12);
}
errors++;
}
}
else {
const err13 = {instancePath:instancePath+"/payload_sha256",schemaPath:"#/$defs/sha256/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err13];
}
else {
vErrors.push(err13);
}
errors++;
}
}
if(data.progress !== undefined && func0.call(data, "progress")){
let data4 = data.progress;
if(data4 && typeof data4 == "object" && !Array.isArray(data4)){
if((data4.step === undefined) || (!(func0.call(data4, "step")))){
const err14 = {instancePath:instancePath+"/progress",schemaPath:"#/$defs/progress/required",keyword:"required",params:{missingProperty: "step"},message:"must have required property '"+"step"+"'"};
if(vErrors === null){
vErrors = [err14];
}
else {
vErrors.push(err14);
}
errors++;
}
if((data4.total_steps === undefined) || (!(func0.call(data4, "total_steps")))){
const err15 = {instancePath:instancePath+"/progress",schemaPath:"#/$defs/progress/required",keyword:"required",params:{missingProperty: "total_steps"},message:"must have required property '"+"total_steps"+"'"};
if(vErrors === null){
vErrors = [err15];
}
else {
vErrors.push(err15);
}
errors++;
}
if((data4.percent === undefined) || (!(func0.call(data4, "percent")))){
const err16 = {instancePath:instancePath+"/progress",schemaPath:"#/$defs/progress/required",keyword:"required",params:{missingProperty: "percent"},message:"must have required property '"+"percent"+"'"};
if(vErrors === null){
vErrors = [err16];
}
else {
vErrors.push(err16);
}
errors++;
}
for(const key1 of Object.keys(data4)){
if(!(((key1 === "step") || (key1 === "total_steps")) || (key1 === "percent"))){
const err17 = {instancePath:instancePath+"/progress",schemaPath:"#/$defs/progress/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key1},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err17];
}
else {
vErrors.push(err17);
}
errors++;
}
}
if(data4.step !== undefined && func0.call(data4, "step")){
let data5 = data4.step;
if(!(((typeof data5 == "number") && (!(data5 % 1) && !isNaN(data5))) && (isFinite(data5)))){
const err18 = {instancePath:instancePath+"/progress/step",schemaPath:"#/$defs/progress/properties/step/type",keyword:"type",params:{type: "integer"},message:"must be integer"};
if(vErrors === null){
vErrors = [err18];
}
else {
vErrors.push(err18);
}
errors++;
}
if((typeof data5 == "number") && (isFinite(data5))){
if(data5 > 9007199254740991 || isNaN(data5)){
const err19 = {instancePath:instancePath+"/progress/step",schemaPath:"#/$defs/progress/properties/step/maximum",keyword:"maximum",params:{comparison: "<=", limit: 9007199254740991},message:"must be <= 9007199254740991"};
if(vErrors === null){
vErrors = [err19];
}
else {
vErrors.push(err19);
}
errors++;
}
if(data5 < 0 || isNaN(data5)){
const err20 = {instancePath:instancePath+"/progress/step",schemaPath:"#/$defs/progress/properties/step/minimum",keyword:"minimum",params:{comparison: ">=", limit: 0},message:"must be >= 0"};
if(vErrors === null){
vErrors = [err20];
}
else {
vErrors.push(err20);
}
errors++;
}
}
}
if(data4.total_steps !== undefined && func0.call(data4, "total_steps")){
let data6 = data4.total_steps;
if(!(((typeof data6 == "number") && (!(data6 % 1) && !isNaN(data6))) && (isFinite(data6)))){
const err21 = {instancePath:instancePath+"/progress/total_steps",schemaPath:"#/$defs/progress/properties/total_steps/type",keyword:"type",params:{type: "integer"},message:"must be integer"};
if(vErrors === null){
vErrors = [err21];
}
else {
vErrors.push(err21);
}
errors++;
}
if((typeof data6 == "number") && (isFinite(data6))){
if(data6 > 9007199254740991 || isNaN(data6)){
const err22 = {instancePath:instancePath+"/progress/total_steps",schemaPath:"#/$defs/progress/properties/total_steps/maximum",keyword:"maximum",params:{comparison: "<=", limit: 9007199254740991},message:"must be <= 9007199254740991"};
if(vErrors === null){
vErrors = [err22];
}
else {
vErrors.push(err22);
}
errors++;
}
if(data6 < 1 || isNaN(data6)){
const err23 = {instancePath:instancePath+"/progress/total_steps",schemaPath:"#/$defs/progress/properties/total_steps/minimum",keyword:"minimum",params:{comparison: ">=", limit: 1},message:"must be >= 1"};
if(vErrors === null){
vErrors = [err23];
}
else {
vErrors.push(err23);
}
errors++;
}
}
}
if(data4.percent !== undefined && func0.call(data4, "percent")){
let data7 = data4.percent;
if((typeof data7 == "number") && (isFinite(data7))){
if(data7 > 100 || isNaN(data7)){
const err24 = {instancePath:instancePath+"/progress/percent",schemaPath:"#/$defs/progress/properties/percent/maximum",keyword:"maximum",params:{comparison: "<=", limit: 100},message:"must be <= 100"};
if(vErrors === null){
vErrors = [err24];
}
else {
vErrors.push(err24);
}
errors++;
}
if(data7 < 0 || isNaN(data7)){
const err25 = {instancePath:instancePath+"/progress/percent",schemaPath:"#/$defs/progress/properties/percent/minimum",keyword:"minimum",params:{comparison: ">=", limit: 0},message:"must be >= 0"};
if(vErrors === null){
vErrors = [err25];
}
else {
vErrors.push(err25);
}
errors++;
}
}
else {
const err26 = {instancePath:instancePath+"/progress/percent",schemaPath:"#/$defs/progress/properties/percent/type",keyword:"type",params:{type: "number"},message:"must be number"};
if(vErrors === null){
vErrors = [err26];
}
else {
vErrors.push(err26);
}
errors++;
}
}
}
else {
const err27 = {instancePath:instancePath+"/progress",schemaPath:"#/$defs/progress/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err27];
}
else {
vErrors.push(err27);
}
errors++;
}
}
}
else {
const err28 = {instancePath,schemaPath:"#/oneOf/0/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err28];
}
else {
vErrors.push(err28);
}
errors++;
}
var _valid0 = _errs1 === errors;
if(_valid0){
valid0 = true;
passing0 = 0;
var props0 = true;
}
const _errs23 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
if((data.event_type === undefined) || (!(func0.call(data, "event_type")))){
const err29 = {instancePath,schemaPath:"#/oneOf/1/required",keyword:"required",params:{missingProperty: "event_type"},message:"must have required property '"+"event_type"+"'"};
if(vErrors === null){
vErrors = [err29];
}
else {
vErrors.push(err29);
}
errors++;
}
if((data.event_id === undefined) || (!(func0.call(data, "event_id")))){
const err30 = {instancePath,schemaPath:"#/oneOf/1/required",keyword:"required",params:{missingProperty: "event_id"},message:"must have required property '"+"event_id"+"'"};
if(vErrors === null){
vErrors = [err30];
}
else {
vErrors.push(err30);
}
errors++;
}
if((data.occurred_at === undefined) || (!(func0.call(data, "occurred_at")))){
const err31 = {instancePath,schemaPath:"#/oneOf/1/required",keyword:"required",params:{missingProperty: "occurred_at"},message:"must have required property '"+"occurred_at"+"'"};
if(vErrors === null){
vErrors = [err31];
}
else {
vErrors.push(err31);
}
errors++;
}
if((data.payload_sha256 === undefined) || (!(func0.call(data, "payload_sha256")))){
const err32 = {instancePath,schemaPath:"#/oneOf/1/required",keyword:"required",params:{missingProperty: "payload_sha256"},message:"must have required property '"+"payload_sha256"+"'"};
if(vErrors === null){
vErrors = [err32];
}
else {
vErrors.push(err32);
}
errors++;
}
if((data.level === undefined) || (!(func0.call(data, "level")))){
const err33 = {instancePath,schemaPath:"#/oneOf/1/required",keyword:"required",params:{missingProperty: "level"},message:"must have required property '"+"level"+"'"};
if(vErrors === null){
vErrors = [err33];
}
else {
vErrors.push(err33);
}
errors++;
}
if((data.message === undefined) || (!(func0.call(data, "message")))){
const err34 = {instancePath,schemaPath:"#/oneOf/1/required",keyword:"required",params:{missingProperty: "message"},message:"must have required property '"+"message"+"'"};
if(vErrors === null){
vErrors = [err34];
}
else {
vErrors.push(err34);
}
errors++;
}
for(const key2 of Object.keys(data)){
if(!((((((key2 === "event_type") || (key2 === "event_id")) || (key2 === "occurred_at")) || (key2 === "payload_sha256")) || (key2 === "level")) || (key2 === "message"))){
const err35 = {instancePath,schemaPath:"#/oneOf/1/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key2},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err35];
}
else {
vErrors.push(err35);
}
errors++;
}
}
if(data.event_type !== undefined && func0.call(data, "event_type")){
if("MESSAGE" !== data.event_type){
const err36 = {instancePath:instancePath+"/event_type",schemaPath:"#/oneOf/1/properties/event_type/const",keyword:"const",params:{allowedValue: "MESSAGE"},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err36];
}
else {
vErrors.push(err36);
}
errors++;
}
}
if(data.event_id !== undefined && func0.call(data, "event_id")){
let data9 = data.event_id;
if(typeof data9 === "string"){
if(func114(data9) < 1){
const err37 = {instancePath:instancePath+"/event_id",schemaPath:"#/oneOf/1/properties/event_id/minLength",keyword:"minLength",params:{limit: 1},message:"must NOT have fewer than 1 characters"};
if(vErrors === null){
vErrors = [err37];
}
else {
vErrors.push(err37);
}
errors++;
}
}
else {
const err38 = {instancePath:instancePath+"/event_id",schemaPath:"#/oneOf/1/properties/event_id/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err38];
}
else {
vErrors.push(err38);
}
errors++;
}
}
if(data.occurred_at !== undefined && func0.call(data, "occurred_at")){
let data10 = data.occurred_at;
if(typeof data10 === "string"){
if(!pattern5.test(data10)){
const err39 = {instancePath:instancePath+"/occurred_at",schemaPath:"#/$defs/utc/pattern",keyword:"pattern",params:{pattern: "^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"},message:"must match pattern \""+"^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"+"\""};
if(vErrors === null){
vErrors = [err39];
}
else {
vErrors.push(err39);
}
errors++;
}
if(!(formats0.validate(data10))){
const err40 = {instancePath:instancePath+"/occurred_at",schemaPath:"#/$defs/utc/format",keyword:"format",params:{format: "date-time"},message:"must match format \""+"date-time"+"\""};
if(vErrors === null){
vErrors = [err40];
}
else {
vErrors.push(err40);
}
errors++;
}
}
else {
const err41 = {instancePath:instancePath+"/occurred_at",schemaPath:"#/$defs/utc/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err41];
}
else {
vErrors.push(err41);
}
errors++;
}
}
if(data.payload_sha256 !== undefined && func0.call(data, "payload_sha256")){
let data11 = data.payload_sha256;
if(typeof data11 === "string"){
if(!pattern4.test(data11)){
const err42 = {instancePath:instancePath+"/payload_sha256",schemaPath:"#/$defs/sha256/pattern",keyword:"pattern",params:{pattern: "^[0-9a-f]{64}$"},message:"must match pattern \""+"^[0-9a-f]{64}$"+"\""};
if(vErrors === null){
vErrors = [err42];
}
else {
vErrors.push(err42);
}
errors++;
}
}
else {
const err43 = {instancePath:instancePath+"/payload_sha256",schemaPath:"#/$defs/sha256/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err43];
}
else {
vErrors.push(err43);
}
errors++;
}
}
if(data.level !== undefined && func0.call(data, "level")){
let data12 = data.level;
if(!((((data12 === "DEBUG") || (data12 === "INFO")) || (data12 === "WARNING")) || (data12 === "ERROR"))){
const err44 = {instancePath:instancePath+"/level",schemaPath:"#/oneOf/1/properties/level/enum",keyword:"enum",params:{allowedValues: schema53.oneOf[1].properties.level.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err44];
}
else {
vErrors.push(err44);
}
errors++;
}
}
if(data.message !== undefined && func0.call(data, "message")){
let data13 = data.message;
if(typeof data13 === "string"){
if(func114(data13) < 1){
const err45 = {instancePath:instancePath+"/message",schemaPath:"#/oneOf/1/properties/message/minLength",keyword:"minLength",params:{limit: 1},message:"must NOT have fewer than 1 characters"};
if(vErrors === null){
vErrors = [err45];
}
else {
vErrors.push(err45);
}
errors++;
}
}
else {
const err46 = {instancePath:instancePath+"/message",schemaPath:"#/oneOf/1/properties/message/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err46];
}
else {
vErrors.push(err46);
}
errors++;
}
}
}
else {
const err47 = {instancePath,schemaPath:"#/oneOf/1/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err47];
}
else {
vErrors.push(err47);
}
errors++;
}
var _valid0 = _errs23 === errors;
if(_valid0 && valid0){
valid0 = false;
passing0 = [passing0, 1];
}
else {
if(_valid0){
valid0 = true;
passing0 = 1;
if(props0 !== true){
props0 = true;
}
}
const _errs38 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
if((data.event_type === undefined) || (!(func0.call(data, "event_type")))){
const err48 = {instancePath,schemaPath:"#/oneOf/2/required",keyword:"required",params:{missingProperty: "event_type"},message:"must have required property '"+"event_type"+"'"};
if(vErrors === null){
vErrors = [err48];
}
else {
vErrors.push(err48);
}
errors++;
}
if((data.event_id === undefined) || (!(func0.call(data, "event_id")))){
const err49 = {instancePath,schemaPath:"#/oneOf/2/required",keyword:"required",params:{missingProperty: "event_id"},message:"must have required property '"+"event_id"+"'"};
if(vErrors === null){
vErrors = [err49];
}
else {
vErrors.push(err49);
}
errors++;
}
if((data.occurred_at === undefined) || (!(func0.call(data, "occurred_at")))){
const err50 = {instancePath,schemaPath:"#/oneOf/2/required",keyword:"required",params:{missingProperty: "occurred_at"},message:"must have required property '"+"occurred_at"+"'"};
if(vErrors === null){
vErrors = [err50];
}
else {
vErrors.push(err50);
}
errors++;
}
if((data.payload_sha256 === undefined) || (!(func0.call(data, "payload_sha256")))){
const err51 = {instancePath,schemaPath:"#/oneOf/2/required",keyword:"required",params:{missingProperty: "payload_sha256"},message:"must have required property '"+"payload_sha256"+"'"};
if(vErrors === null){
vErrors = [err51];
}
else {
vErrors.push(err51);
}
errors++;
}
if((data.artifact_id === undefined) || (!(func0.call(data, "artifact_id")))){
const err52 = {instancePath,schemaPath:"#/oneOf/2/required",keyword:"required",params:{missingProperty: "artifact_id"},message:"must have required property '"+"artifact_id"+"'"};
if(vErrors === null){
vErrors = [err52];
}
else {
vErrors.push(err52);
}
errors++;
}
for(const key3 of Object.keys(data)){
if(!(((((key3 === "event_type") || (key3 === "event_id")) || (key3 === "occurred_at")) || (key3 === "payload_sha256")) || (key3 === "artifact_id"))){
const err53 = {instancePath,schemaPath:"#/oneOf/2/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key3},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err53];
}
else {
vErrors.push(err53);
}
errors++;
}
}
if(data.event_type !== undefined && func0.call(data, "event_type")){
if("ARTIFACT" !== data.event_type){
const err54 = {instancePath:instancePath+"/event_type",schemaPath:"#/oneOf/2/properties/event_type/const",keyword:"const",params:{allowedValue: "ARTIFACT"},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err54];
}
else {
vErrors.push(err54);
}
errors++;
}
}
if(data.event_id !== undefined && func0.call(data, "event_id")){
let data15 = data.event_id;
if(typeof data15 === "string"){
if(func114(data15) < 1){
const err55 = {instancePath:instancePath+"/event_id",schemaPath:"#/oneOf/2/properties/event_id/minLength",keyword:"minLength",params:{limit: 1},message:"must NOT have fewer than 1 characters"};
if(vErrors === null){
vErrors = [err55];
}
else {
vErrors.push(err55);
}
errors++;
}
}
else {
const err56 = {instancePath:instancePath+"/event_id",schemaPath:"#/oneOf/2/properties/event_id/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err56];
}
else {
vErrors.push(err56);
}
errors++;
}
}
if(data.occurred_at !== undefined && func0.call(data, "occurred_at")){
let data16 = data.occurred_at;
if(typeof data16 === "string"){
if(!pattern5.test(data16)){
const err57 = {instancePath:instancePath+"/occurred_at",schemaPath:"#/$defs/utc/pattern",keyword:"pattern",params:{pattern: "^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"},message:"must match pattern \""+"^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"+"\""};
if(vErrors === null){
vErrors = [err57];
}
else {
vErrors.push(err57);
}
errors++;
}
if(!(formats0.validate(data16))){
const err58 = {instancePath:instancePath+"/occurred_at",schemaPath:"#/$defs/utc/format",keyword:"format",params:{format: "date-time"},message:"must match format \""+"date-time"+"\""};
if(vErrors === null){
vErrors = [err58];
}
else {
vErrors.push(err58);
}
errors++;
}
}
else {
const err59 = {instancePath:instancePath+"/occurred_at",schemaPath:"#/$defs/utc/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err59];
}
else {
vErrors.push(err59);
}
errors++;
}
}
if(data.payload_sha256 !== undefined && func0.call(data, "payload_sha256")){
let data17 = data.payload_sha256;
if(typeof data17 === "string"){
if(!pattern4.test(data17)){
const err60 = {instancePath:instancePath+"/payload_sha256",schemaPath:"#/$defs/sha256/pattern",keyword:"pattern",params:{pattern: "^[0-9a-f]{64}$"},message:"must match pattern \""+"^[0-9a-f]{64}$"+"\""};
if(vErrors === null){
vErrors = [err60];
}
else {
vErrors.push(err60);
}
errors++;
}
}
else {
const err61 = {instancePath:instancePath+"/payload_sha256",schemaPath:"#/$defs/sha256/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err61];
}
else {
vErrors.push(err61);
}
errors++;
}
}
if(data.artifact_id !== undefined && func0.call(data, "artifact_id")){
let data18 = data.artifact_id;
if(typeof data18 === "string"){
if(!pattern20.test(data18)){
const err62 = {instancePath:instancePath+"/artifact_id",schemaPath:"#/$defs/artifactId/pattern",keyword:"pattern",params:{pattern: "^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"},message:"must match pattern \""+"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"+"\""};
if(vErrors === null){
vErrors = [err62];
}
else {
vErrors.push(err62);
}
errors++;
}
}
else {
const err63 = {instancePath:instancePath+"/artifact_id",schemaPath:"#/$defs/artifactId/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err63];
}
else {
vErrors.push(err63);
}
errors++;
}
}
}
else {
const err64 = {instancePath,schemaPath:"#/oneOf/2/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err64];
}
else {
vErrors.push(err64);
}
errors++;
}
var _valid0 = _errs38 === errors;
if(_valid0 && valid0){
valid0 = false;
passing0 = [passing0, 2];
}
else {
if(_valid0){
valid0 = true;
passing0 = 2;
if(props0 !== true){
props0 = true;
}
}
const _errs53 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
if((data.event_type === undefined) || (!(func0.call(data, "event_type")))){
const err65 = {instancePath,schemaPath:"#/oneOf/3/required",keyword:"required",params:{missingProperty: "event_type"},message:"must have required property '"+"event_type"+"'"};
if(vErrors === null){
vErrors = [err65];
}
else {
vErrors.push(err65);
}
errors++;
}
if((data.event_id === undefined) || (!(func0.call(data, "event_id")))){
const err66 = {instancePath,schemaPath:"#/oneOf/3/required",keyword:"required",params:{missingProperty: "event_id"},message:"must have required property '"+"event_id"+"'"};
if(vErrors === null){
vErrors = [err66];
}
else {
vErrors.push(err66);
}
errors++;
}
if((data.occurred_at === undefined) || (!(func0.call(data, "occurred_at")))){
const err67 = {instancePath,schemaPath:"#/oneOf/3/required",keyword:"required",params:{missingProperty: "occurred_at"},message:"must have required property '"+"occurred_at"+"'"};
if(vErrors === null){
vErrors = [err67];
}
else {
vErrors.push(err67);
}
errors++;
}
if((data.payload_sha256 === undefined) || (!(func0.call(data, "payload_sha256")))){
const err68 = {instancePath,schemaPath:"#/oneOf/3/required",keyword:"required",params:{missingProperty: "payload_sha256"},message:"must have required property '"+"payload_sha256"+"'"};
if(vErrors === null){
vErrors = [err68];
}
else {
vErrors.push(err68);
}
errors++;
}
if((data.state === undefined) || (!(func0.call(data, "state")))){
const err69 = {instancePath,schemaPath:"#/oneOf/3/required",keyword:"required",params:{missingProperty: "state"},message:"must have required property '"+"state"+"'"};
if(vErrors === null){
vErrors = [err69];
}
else {
vErrors.push(err69);
}
errors++;
}
for(const key4 of Object.keys(data)){
if(!(((((key4 === "event_type") || (key4 === "event_id")) || (key4 === "occurred_at")) || (key4 === "payload_sha256")) || (key4 === "state"))){
const err70 = {instancePath,schemaPath:"#/oneOf/3/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key4},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err70];
}
else {
vErrors.push(err70);
}
errors++;
}
}
if(data.event_type !== undefined && func0.call(data, "event_type")){
if("STATE" !== data.event_type){
const err71 = {instancePath:instancePath+"/event_type",schemaPath:"#/oneOf/3/properties/event_type/const",keyword:"const",params:{allowedValue: "STATE"},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err71];
}
else {
vErrors.push(err71);
}
errors++;
}
}
if(data.event_id !== undefined && func0.call(data, "event_id")){
let data20 = data.event_id;
if(typeof data20 === "string"){
if(func114(data20) < 1){
const err72 = {instancePath:instancePath+"/event_id",schemaPath:"#/oneOf/3/properties/event_id/minLength",keyword:"minLength",params:{limit: 1},message:"must NOT have fewer than 1 characters"};
if(vErrors === null){
vErrors = [err72];
}
else {
vErrors.push(err72);
}
errors++;
}
}
else {
const err73 = {instancePath:instancePath+"/event_id",schemaPath:"#/oneOf/3/properties/event_id/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err73];
}
else {
vErrors.push(err73);
}
errors++;
}
}
if(data.occurred_at !== undefined && func0.call(data, "occurred_at")){
let data21 = data.occurred_at;
if(typeof data21 === "string"){
if(!pattern5.test(data21)){
const err74 = {instancePath:instancePath+"/occurred_at",schemaPath:"#/$defs/utc/pattern",keyword:"pattern",params:{pattern: "^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"},message:"must match pattern \""+"^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"+"\""};
if(vErrors === null){
vErrors = [err74];
}
else {
vErrors.push(err74);
}
errors++;
}
if(!(formats0.validate(data21))){
const err75 = {instancePath:instancePath+"/occurred_at",schemaPath:"#/$defs/utc/format",keyword:"format",params:{format: "date-time"},message:"must match format \""+"date-time"+"\""};
if(vErrors === null){
vErrors = [err75];
}
else {
vErrors.push(err75);
}
errors++;
}
}
else {
const err76 = {instancePath:instancePath+"/occurred_at",schemaPath:"#/$defs/utc/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err76];
}
else {
vErrors.push(err76);
}
errors++;
}
}
if(data.payload_sha256 !== undefined && func0.call(data, "payload_sha256")){
let data22 = data.payload_sha256;
if(typeof data22 === "string"){
if(!pattern4.test(data22)){
const err77 = {instancePath:instancePath+"/payload_sha256",schemaPath:"#/$defs/sha256/pattern",keyword:"pattern",params:{pattern: "^[0-9a-f]{64}$"},message:"must match pattern \""+"^[0-9a-f]{64}$"+"\""};
if(vErrors === null){
vErrors = [err77];
}
else {
vErrors.push(err77);
}
errors++;
}
}
else {
const err78 = {instancePath:instancePath+"/payload_sha256",schemaPath:"#/$defs/sha256/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err78];
}
else {
vErrors.push(err78);
}
errors++;
}
}
if(data.state !== undefined && func0.call(data, "state")){
if(!(validate25(data.state, {instancePath:instancePath+"/state",parentData:data,parentDataProperty:"state",rootData,dynamicAnchors}))){
vErrors = vErrors === null ? validate25.errors : vErrors.concat(validate25.errors);
errors = vErrors.length;
}
}
}
else {
const err79 = {instancePath,schemaPath:"#/oneOf/3/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err79];
}
else {
vErrors.push(err79);
}
errors++;
}
var _valid0 = _errs53 === errors;
if(_valid0 && valid0){
valid0 = false;
passing0 = [passing0, 3];
}
else {
if(_valid0){
valid0 = true;
passing0 = 3;
if(props0 !== true){
props0 = true;
}
}
}
}
}
if(!valid0){
const err80 = {instancePath,schemaPath:"#/oneOf",keyword:"oneOf",params:{passingSchemas: passing0},message:"must match exactly one schema in oneOf"};
if(vErrors === null){
vErrors = [err80];
}
else {
vErrors.push(err80);
}
errors++;
}
else {
errors = _errs0;
if(vErrors !== null){
if(_errs0){
vErrors.length = _errs0;
}
else {
vErrors = null;
}
}
}
validate35.errors = vErrors;
evaluated0.props = props0;
return errors === 0;
}
validate35.evaluated = {"dynamicProps":true,"dynamicItems":false};


function validate80(data, {instancePath="", parentData, parentDataProperty, rootData=data, dynamicAnchors={}}={}){
let vErrors = null;
let errors = 0;
const evaluated0 = validate80.evaluated;
if(evaluated0.dynamicProps){
evaluated0.props = undefined;
}
if(evaluated0.dynamicItems){
evaluated0.items = undefined;
}
if(data && typeof data == "object" && !Array.isArray(data)){
if((data.route_id === undefined) || (!(func0.call(data, "route_id")))){
const err0 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "route_id"},message:"must have required property '"+"route_id"+"'"};
if(vErrors === null){
vErrors = [err0];
}
else {
vErrors.push(err0);
}
errors++;
}
if((data.source === undefined) || (!(func0.call(data, "source")))){
const err1 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "source"},message:"must have required property '"+"source"+"'"};
if(vErrors === null){
vErrors = [err1];
}
else {
vErrors.push(err1);
}
errors++;
}
if((data.list === undefined) || (!(func0.call(data, "list")))){
const err2 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "list"},message:"must have required property '"+"list"+"'"};
if(vErrors === null){
vErrors = [err2];
}
else {
vErrors.push(err2);
}
errors++;
}
if((data.locks === undefined) || (!(func0.call(data, "locks")))){
const err3 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "locks"},message:"must have required property '"+"locks"+"'"};
if(vErrors === null){
vErrors = [err3];
}
else {
vErrors.push(err3);
}
errors++;
}
if((data.run_id === undefined) || (!(func0.call(data, "run_id")))){
const err4 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "run_id"},message:"must have required property '"+"run_id"+"'"};
if(vErrors === null){
vErrors = [err4];
}
else {
vErrors.push(err4);
}
errors++;
}
for(const key0 of Object.keys(data)){
if(!(((((key0 === "route_id") || (key0 === "source")) || (key0 === "locks")) || (key0 === "list")) || (key0 === "run_id"))){
const err5 = {instancePath,schemaPath:"#/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key0},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err5];
}
else {
vErrors.push(err5);
}
errors++;
}
}
if(data.route_id !== undefined && func0.call(data, "route_id")){
if("EVENTS" !== data.route_id){
const err6 = {instancePath:instancePath+"/route_id",schemaPath:"#/properties/route_id/const",keyword:"const",params:{allowedValue: "EVENTS"},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err6];
}
else {
vErrors.push(err6);
}
errors++;
}
}
if(data.source !== undefined && func0.call(data, "source")){
if(!(validate22(data.source, {instancePath:instancePath+"/source",parentData:data,parentDataProperty:"source",rootData,dynamicAnchors}))){
vErrors = vErrors === null ? validate22.errors : vErrors.concat(validate22.errors);
errors = vErrors.length;
}
}
if(data.locks !== undefined && func0.call(data, "locks")){
let data2 = data.locks;
if(data2 && typeof data2 == "object" && !Array.isArray(data2)){
if((data2.promotion_allowed === undefined) || (!(func0.call(data2, "promotion_allowed")))){
const err7 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "promotion_allowed"},message:"must have required property '"+"promotion_allowed"+"'"};
if(vErrors === null){
vErrors = [err7];
}
else {
vErrors.push(err7);
}
errors++;
}
if((data2.model_build_allowed === undefined) || (!(func0.call(data2, "model_build_allowed")))){
const err8 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "model_build_allowed"},message:"must have required property '"+"model_build_allowed"+"'"};
if(vErrors === null){
vErrors = [err8];
}
else {
vErrors.push(err8);
}
errors++;
}
if((data2.paper_forward_allowed === undefined) || (!(func0.call(data2, "paper_forward_allowed")))){
const err9 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "paper_forward_allowed"},message:"must have required property '"+"paper_forward_allowed"+"'"};
if(vErrors === null){
vErrors = [err9];
}
else {
vErrors.push(err9);
}
errors++;
}
if((data2.live_broker_order_allowed === undefined) || (!(func0.call(data2, "live_broker_order_allowed")))){
const err10 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "live_broker_order_allowed"},message:"must have required property '"+"live_broker_order_allowed"+"'"};
if(vErrors === null){
vErrors = [err10];
}
else {
vErrors.push(err10);
}
errors++;
}
if((data2.profitability_claim_allowed === undefined) || (!(func0.call(data2, "profitability_claim_allowed")))){
const err11 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "profitability_claim_allowed"},message:"must have required property '"+"profitability_claim_allowed"+"'"};
if(vErrors === null){
vErrors = [err11];
}
else {
vErrors.push(err11);
}
errors++;
}
if((data2.go_summary_allowed === undefined) || (!(func0.call(data2, "go_summary_allowed")))){
const err12 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "go_summary_allowed"},message:"must have required property '"+"go_summary_allowed"+"'"};
if(vErrors === null){
vErrors = [err12];
}
else {
vErrors.push(err12);
}
errors++;
}
for(const key1 of Object.keys(data2)){
if(!((((((key1 === "promotion_allowed") || (key1 === "model_build_allowed")) || (key1 === "paper_forward_allowed")) || (key1 === "live_broker_order_allowed")) || (key1 === "profitability_claim_allowed")) || (key1 === "go_summary_allowed"))){
const err13 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key1},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err13];
}
else {
vErrors.push(err13);
}
errors++;
}
}
if(data2.promotion_allowed !== undefined && func0.call(data2, "promotion_allowed")){
if(false !== data2.promotion_allowed){
const err14 = {instancePath:instancePath+"/locks/promotion_allowed",schemaPath:"#/$defs/locks/properties/promotion_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err14];
}
else {
vErrors.push(err14);
}
errors++;
}
}
if(data2.model_build_allowed !== undefined && func0.call(data2, "model_build_allowed")){
if(false !== data2.model_build_allowed){
const err15 = {instancePath:instancePath+"/locks/model_build_allowed",schemaPath:"#/$defs/locks/properties/model_build_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err15];
}
else {
vErrors.push(err15);
}
errors++;
}
}
if(data2.paper_forward_allowed !== undefined && func0.call(data2, "paper_forward_allowed")){
if(false !== data2.paper_forward_allowed){
const err16 = {instancePath:instancePath+"/locks/paper_forward_allowed",schemaPath:"#/$defs/locks/properties/paper_forward_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err16];
}
else {
vErrors.push(err16);
}
errors++;
}
}
if(data2.live_broker_order_allowed !== undefined && func0.call(data2, "live_broker_order_allowed")){
if(false !== data2.live_broker_order_allowed){
const err17 = {instancePath:instancePath+"/locks/live_broker_order_allowed",schemaPath:"#/$defs/locks/properties/live_broker_order_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err17];
}
else {
vErrors.push(err17);
}
errors++;
}
}
if(data2.profitability_claim_allowed !== undefined && func0.call(data2, "profitability_claim_allowed")){
if(false !== data2.profitability_claim_allowed){
const err18 = {instancePath:instancePath+"/locks/profitability_claim_allowed",schemaPath:"#/$defs/locks/properties/profitability_claim_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err18];
}
else {
vErrors.push(err18);
}
errors++;
}
}
if(data2.go_summary_allowed !== undefined && func0.call(data2, "go_summary_allowed")){
if(false !== data2.go_summary_allowed){
const err19 = {instancePath:instancePath+"/locks/go_summary_allowed",schemaPath:"#/$defs/locks/properties/go_summary_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err19];
}
else {
vErrors.push(err19);
}
errors++;
}
}
}
else {
const err20 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err20];
}
else {
vErrors.push(err20);
}
errors++;
}
}
if(data.list !== undefined && func0.call(data, "list")){
let data9 = data.list;
if(data9 && typeof data9 == "object" && !Array.isArray(data9)){
if((data9.items === undefined) || (!(func0.call(data9, "items")))){
const err21 = {instancePath:instancePath+"/list",schemaPath:"#/properties/list/required",keyword:"required",params:{missingProperty: "items"},message:"must have required property '"+"items"+"'"};
if(vErrors === null){
vErrors = [err21];
}
else {
vErrors.push(err21);
}
errors++;
}
if((data9.next_cursor === undefined) || (!(func0.call(data9, "next_cursor")))){
const err22 = {instancePath:instancePath+"/list",schemaPath:"#/properties/list/required",keyword:"required",params:{missingProperty: "next_cursor"},message:"must have required property '"+"next_cursor"+"'"};
if(vErrors === null){
vErrors = [err22];
}
else {
vErrors.push(err22);
}
errors++;
}
for(const key2 of Object.keys(data9)){
if(!((key2 === "items") || (key2 === "next_cursor"))){
const err23 = {instancePath:instancePath+"/list",schemaPath:"#/properties/list/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key2},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err23];
}
else {
vErrors.push(err23);
}
errors++;
}
}
if(data9.items !== undefined && func0.call(data9, "items")){
let data10 = data9.items;
if(Array.isArray(data10)){
if(data10.length > 100){
const err24 = {instancePath:instancePath+"/list/items",schemaPath:"#/properties/list/properties/items/maxItems",keyword:"maxItems",params:{limit: 100},message:"must NOT have more than 100 items"};
if(vErrors === null){
vErrors = [err24];
}
else {
vErrors.push(err24);
}
errors++;
}
const len0 = data10.length;
for(let i0=0; i0<len0; i0++){
if(!(validate35(data10[i0], {instancePath:instancePath+"/list/items/" + i0,parentData:data10,parentDataProperty:i0,rootData,dynamicAnchors}))){
vErrors = vErrors === null ? validate35.errors : vErrors.concat(validate35.errors);
errors = vErrors.length;
}
}
}
else {
const err25 = {instancePath:instancePath+"/list/items",schemaPath:"#/properties/list/properties/items/type",keyword:"type",params:{type: "array"},message:"must be array"};
if(vErrors === null){
vErrors = [err25];
}
else {
vErrors.push(err25);
}
errors++;
}
}
if(data9.next_cursor !== undefined && func0.call(data9, "next_cursor")){
let data12 = data9.next_cursor;
const _errs21 = errors;
let valid6 = false;
const _errs22 = errors;
if(typeof data12 === "string"){
if(func114(data12) > 2048){
const err26 = {instancePath:instancePath+"/list/next_cursor",schemaPath:"#/$defs/cursor/maxLength",keyword:"maxLength",params:{limit: 2048},message:"must NOT have more than 2048 characters"};
if(vErrors === null){
vErrors = [err26];
}
else {
vErrors.push(err26);
}
errors++;
}
if(func114(data12) < 16){
const err27 = {instancePath:instancePath+"/list/next_cursor",schemaPath:"#/$defs/cursor/minLength",keyword:"minLength",params:{limit: 16},message:"must NOT have fewer than 16 characters"};
if(vErrors === null){
vErrors = [err27];
}
else {
vErrors.push(err27);
}
errors++;
}
if(!pattern13.test(data12)){
const err28 = {instancePath:instancePath+"/list/next_cursor",schemaPath:"#/$defs/cursor/pattern",keyword:"pattern",params:{pattern: "^[A-Za-z0-9_-]+$"},message:"must match pattern \""+"^[A-Za-z0-9_-]+$"+"\""};
if(vErrors === null){
vErrors = [err28];
}
else {
vErrors.push(err28);
}
errors++;
}
}
else {
const err29 = {instancePath:instancePath+"/list/next_cursor",schemaPath:"#/$defs/cursor/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err29];
}
else {
vErrors.push(err29);
}
errors++;
}
var _valid0 = _errs22 === errors;
valid6 = valid6 || _valid0;
const _errs25 = errors;
if(data12 !== null){
const err30 = {instancePath:instancePath+"/list/next_cursor",schemaPath:"#/properties/list/properties/next_cursor/anyOf/1/type",keyword:"type",params:{type: "null"},message:"must be null"};
if(vErrors === null){
vErrors = [err30];
}
else {
vErrors.push(err30);
}
errors++;
}
var _valid0 = _errs25 === errors;
valid6 = valid6 || _valid0;
if(!valid6){
const err31 = {instancePath:instancePath+"/list/next_cursor",schemaPath:"#/properties/list/properties/next_cursor/anyOf",keyword:"anyOf",params:{},message:"must match a schema in anyOf"};
if(vErrors === null){
vErrors = [err31];
}
else {
vErrors.push(err31);
}
errors++;
}
else {
errors = _errs21;
if(vErrors !== null){
if(_errs21){
vErrors.length = _errs21;
}
else {
vErrors = null;
}
}
}
}
}
else {
const err32 = {instancePath:instancePath+"/list",schemaPath:"#/properties/list/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err32];
}
else {
vErrors.push(err32);
}
errors++;
}
}
if(data.run_id !== undefined && func0.call(data, "run_id")){
let data13 = data.run_id;
if(typeof data13 === "string"){
if(!pattern6.test(data13)){
const err33 = {instancePath:instancePath+"/run_id",schemaPath:"#/$defs/runId/pattern",keyword:"pattern",params:{pattern: "^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"},message:"must match pattern \""+"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"+"\""};
if(vErrors === null){
vErrors = [err33];
}
else {
vErrors.push(err33);
}
errors++;
}
}
else {
const err34 = {instancePath:instancePath+"/run_id",schemaPath:"#/$defs/runId/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err34];
}
else {
vErrors.push(err34);
}
errors++;
}
}
}
else {
const err35 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err35];
}
else {
vErrors.push(err35);
}
errors++;
}
validate80.errors = vErrors;
return errors === 0;
}
validate80.evaluated = {"props":true,"dynamicProps":false,"dynamicItems":false};

export const validateMatrixRoot = validate83;
const schema66 = {"type":"object","additionalProperties":false,"required":["route_id","source","cells","summary","locks"],"properties":{"route_id":{"const":"MATRIX"},"source":{"$ref":"#/$defs/source"},"locks":{"$ref":"#/$defs/locks"},"cells":{"$ref":"#/$defs/matrixCells"},"summary":{"$ref":"#/$defs/matrixSummary"}}};
const schema70 = {"type":"object","additionalProperties":false,"required":["total_cells","pass_count","fail_count","blocked_count","pending_count"],"properties":{"total_cells":{"const":50},"pass_count":{"type":"integer","minimum":0},"fail_count":{"type":"integer","minimum":0},"blocked_count":{"type":"integer","minimum":0},"pending_count":{"type":"integer","minimum":0}}};
const schema68 = {"type":"array","minItems":50,"maxItems":50,"items":{"$ref":"#/$defs/matrixCell"}};
const schema69 = {"type":"object","additionalProperties":false,"required":["row_id","column_id","state"],"properties":{"row_id":{"enum":["seed-01","seed-02","seed-03","seed-04","seed-05"]},"column_id":{"enum":["fold-01:baseline","fold-01:cost-00bp","fold-01:cost-23bp","fold-01:cost-46bp","fold-01:no-trade","fold-02:baseline","fold-02:cost-00bp","fold-02:cost-23bp","fold-02:cost-46bp","fold-02:no-trade"]},"state":{"enum":["PASS","FAIL","BLOCKED","PENDING"]}}};

function validate41(data, {instancePath="", parentData, parentDataProperty, rootData=data, dynamicAnchors={}}={}){
let vErrors = null;
let errors = 0;
const evaluated0 = validate41.evaluated;
if(evaluated0.dynamicProps){
evaluated0.props = undefined;
}
if(evaluated0.dynamicItems){
evaluated0.items = undefined;
}
if(Array.isArray(data)){
if(data.length > 50){
const err0 = {instancePath,schemaPath:"#/maxItems",keyword:"maxItems",params:{limit: 50},message:"must NOT have more than 50 items"};
if(vErrors === null){
vErrors = [err0];
}
else {
vErrors.push(err0);
}
errors++;
}
if(data.length < 50){
const err1 = {instancePath,schemaPath:"#/minItems",keyword:"minItems",params:{limit: 50},message:"must NOT have fewer than 50 items"};
if(vErrors === null){
vErrors = [err1];
}
else {
vErrors.push(err1);
}
errors++;
}
const len0 = data.length;
for(let i0=0; i0<len0; i0++){
let data0 = data[i0];
if(data0 && typeof data0 == "object" && !Array.isArray(data0)){
if((data0.row_id === undefined) || (!(func0.call(data0, "row_id")))){
const err2 = {instancePath:instancePath+"/" + i0,schemaPath:"#/$defs/matrixCell/required",keyword:"required",params:{missingProperty: "row_id"},message:"must have required property '"+"row_id"+"'"};
if(vErrors === null){
vErrors = [err2];
}
else {
vErrors.push(err2);
}
errors++;
}
if((data0.column_id === undefined) || (!(func0.call(data0, "column_id")))){
const err3 = {instancePath:instancePath+"/" + i0,schemaPath:"#/$defs/matrixCell/required",keyword:"required",params:{missingProperty: "column_id"},message:"must have required property '"+"column_id"+"'"};
if(vErrors === null){
vErrors = [err3];
}
else {
vErrors.push(err3);
}
errors++;
}
if((data0.state === undefined) || (!(func0.call(data0, "state")))){
const err4 = {instancePath:instancePath+"/" + i0,schemaPath:"#/$defs/matrixCell/required",keyword:"required",params:{missingProperty: "state"},message:"must have required property '"+"state"+"'"};
if(vErrors === null){
vErrors = [err4];
}
else {
vErrors.push(err4);
}
errors++;
}
for(const key0 of Object.keys(data0)){
if(!(((key0 === "row_id") || (key0 === "column_id")) || (key0 === "state"))){
const err5 = {instancePath:instancePath+"/" + i0,schemaPath:"#/$defs/matrixCell/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key0},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err5];
}
else {
vErrors.push(err5);
}
errors++;
}
}
if(data0.row_id !== undefined && func0.call(data0, "row_id")){
let data1 = data0.row_id;
if(!(((((data1 === "seed-01") || (data1 === "seed-02")) || (data1 === "seed-03")) || (data1 === "seed-04")) || (data1 === "seed-05"))){
const err6 = {instancePath:instancePath+"/" + i0+"/row_id",schemaPath:"#/$defs/matrixCell/properties/row_id/enum",keyword:"enum",params:{allowedValues: schema69.properties.row_id.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err6];
}
else {
vErrors.push(err6);
}
errors++;
}
}
if(data0.column_id !== undefined && func0.call(data0, "column_id")){
let data2 = data0.column_id;
if(!((((((((((data2 === "fold-01:baseline") || (data2 === "fold-01:cost-00bp")) || (data2 === "fold-01:cost-23bp")) || (data2 === "fold-01:cost-46bp")) || (data2 === "fold-01:no-trade")) || (data2 === "fold-02:baseline")) || (data2 === "fold-02:cost-00bp")) || (data2 === "fold-02:cost-23bp")) || (data2 === "fold-02:cost-46bp")) || (data2 === "fold-02:no-trade"))){
const err7 = {instancePath:instancePath+"/" + i0+"/column_id",schemaPath:"#/$defs/matrixCell/properties/column_id/enum",keyword:"enum",params:{allowedValues: schema69.properties.column_id.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err7];
}
else {
vErrors.push(err7);
}
errors++;
}
}
if(data0.state !== undefined && func0.call(data0, "state")){
let data3 = data0.state;
if(!((((data3 === "PASS") || (data3 === "FAIL")) || (data3 === "BLOCKED")) || (data3 === "PENDING"))){
const err8 = {instancePath:instancePath+"/" + i0+"/state",schemaPath:"#/$defs/matrixCell/properties/state/enum",keyword:"enum",params:{allowedValues: schema69.properties.state.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err8];
}
else {
vErrors.push(err8);
}
errors++;
}
}
}
else {
const err9 = {instancePath:instancePath+"/" + i0,schemaPath:"#/$defs/matrixCell/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err9];
}
else {
vErrors.push(err9);
}
errors++;
}
}
}
else {
const err10 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "array"},message:"must be array"};
if(vErrors === null){
vErrors = [err10];
}
else {
vErrors.push(err10);
}
errors++;
}
validate41.errors = vErrors;
return errors === 0;
}
validate41.evaluated = {"items":true,"dynamicProps":false,"dynamicItems":false};


function validate83(data, {instancePath="", parentData, parentDataProperty, rootData=data, dynamicAnchors={}}={}){
let vErrors = null;
let errors = 0;
const evaluated0 = validate83.evaluated;
if(evaluated0.dynamicProps){
evaluated0.props = undefined;
}
if(evaluated0.dynamicItems){
evaluated0.items = undefined;
}
if(data && typeof data == "object" && !Array.isArray(data)){
if((data.route_id === undefined) || (!(func0.call(data, "route_id")))){
const err0 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "route_id"},message:"must have required property '"+"route_id"+"'"};
if(vErrors === null){
vErrors = [err0];
}
else {
vErrors.push(err0);
}
errors++;
}
if((data.source === undefined) || (!(func0.call(data, "source")))){
const err1 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "source"},message:"must have required property '"+"source"+"'"};
if(vErrors === null){
vErrors = [err1];
}
else {
vErrors.push(err1);
}
errors++;
}
if((data.cells === undefined) || (!(func0.call(data, "cells")))){
const err2 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "cells"},message:"must have required property '"+"cells"+"'"};
if(vErrors === null){
vErrors = [err2];
}
else {
vErrors.push(err2);
}
errors++;
}
if((data.summary === undefined) || (!(func0.call(data, "summary")))){
const err3 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "summary"},message:"must have required property '"+"summary"+"'"};
if(vErrors === null){
vErrors = [err3];
}
else {
vErrors.push(err3);
}
errors++;
}
if((data.locks === undefined) || (!(func0.call(data, "locks")))){
const err4 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "locks"},message:"must have required property '"+"locks"+"'"};
if(vErrors === null){
vErrors = [err4];
}
else {
vErrors.push(err4);
}
errors++;
}
for(const key0 of Object.keys(data)){
if(!(((((key0 === "route_id") || (key0 === "source")) || (key0 === "locks")) || (key0 === "cells")) || (key0 === "summary"))){
const err5 = {instancePath,schemaPath:"#/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key0},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err5];
}
else {
vErrors.push(err5);
}
errors++;
}
}
if(data.route_id !== undefined && func0.call(data, "route_id")){
if("MATRIX" !== data.route_id){
const err6 = {instancePath:instancePath+"/route_id",schemaPath:"#/properties/route_id/const",keyword:"const",params:{allowedValue: "MATRIX"},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err6];
}
else {
vErrors.push(err6);
}
errors++;
}
}
if(data.source !== undefined && func0.call(data, "source")){
if(!(validate22(data.source, {instancePath:instancePath+"/source",parentData:data,parentDataProperty:"source",rootData,dynamicAnchors}))){
vErrors = vErrors === null ? validate22.errors : vErrors.concat(validate22.errors);
errors = vErrors.length;
}
}
if(data.locks !== undefined && func0.call(data, "locks")){
let data2 = data.locks;
if(data2 && typeof data2 == "object" && !Array.isArray(data2)){
if((data2.promotion_allowed === undefined) || (!(func0.call(data2, "promotion_allowed")))){
const err7 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "promotion_allowed"},message:"must have required property '"+"promotion_allowed"+"'"};
if(vErrors === null){
vErrors = [err7];
}
else {
vErrors.push(err7);
}
errors++;
}
if((data2.model_build_allowed === undefined) || (!(func0.call(data2, "model_build_allowed")))){
const err8 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "model_build_allowed"},message:"must have required property '"+"model_build_allowed"+"'"};
if(vErrors === null){
vErrors = [err8];
}
else {
vErrors.push(err8);
}
errors++;
}
if((data2.paper_forward_allowed === undefined) || (!(func0.call(data2, "paper_forward_allowed")))){
const err9 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "paper_forward_allowed"},message:"must have required property '"+"paper_forward_allowed"+"'"};
if(vErrors === null){
vErrors = [err9];
}
else {
vErrors.push(err9);
}
errors++;
}
if((data2.live_broker_order_allowed === undefined) || (!(func0.call(data2, "live_broker_order_allowed")))){
const err10 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "live_broker_order_allowed"},message:"must have required property '"+"live_broker_order_allowed"+"'"};
if(vErrors === null){
vErrors = [err10];
}
else {
vErrors.push(err10);
}
errors++;
}
if((data2.profitability_claim_allowed === undefined) || (!(func0.call(data2, "profitability_claim_allowed")))){
const err11 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "profitability_claim_allowed"},message:"must have required property '"+"profitability_claim_allowed"+"'"};
if(vErrors === null){
vErrors = [err11];
}
else {
vErrors.push(err11);
}
errors++;
}
if((data2.go_summary_allowed === undefined) || (!(func0.call(data2, "go_summary_allowed")))){
const err12 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "go_summary_allowed"},message:"must have required property '"+"go_summary_allowed"+"'"};
if(vErrors === null){
vErrors = [err12];
}
else {
vErrors.push(err12);
}
errors++;
}
for(const key1 of Object.keys(data2)){
if(!((((((key1 === "promotion_allowed") || (key1 === "model_build_allowed")) || (key1 === "paper_forward_allowed")) || (key1 === "live_broker_order_allowed")) || (key1 === "profitability_claim_allowed")) || (key1 === "go_summary_allowed"))){
const err13 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key1},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err13];
}
else {
vErrors.push(err13);
}
errors++;
}
}
if(data2.promotion_allowed !== undefined && func0.call(data2, "promotion_allowed")){
if(false !== data2.promotion_allowed){
const err14 = {instancePath:instancePath+"/locks/promotion_allowed",schemaPath:"#/$defs/locks/properties/promotion_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err14];
}
else {
vErrors.push(err14);
}
errors++;
}
}
if(data2.model_build_allowed !== undefined && func0.call(data2, "model_build_allowed")){
if(false !== data2.model_build_allowed){
const err15 = {instancePath:instancePath+"/locks/model_build_allowed",schemaPath:"#/$defs/locks/properties/model_build_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err15];
}
else {
vErrors.push(err15);
}
errors++;
}
}
if(data2.paper_forward_allowed !== undefined && func0.call(data2, "paper_forward_allowed")){
if(false !== data2.paper_forward_allowed){
const err16 = {instancePath:instancePath+"/locks/paper_forward_allowed",schemaPath:"#/$defs/locks/properties/paper_forward_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err16];
}
else {
vErrors.push(err16);
}
errors++;
}
}
if(data2.live_broker_order_allowed !== undefined && func0.call(data2, "live_broker_order_allowed")){
if(false !== data2.live_broker_order_allowed){
const err17 = {instancePath:instancePath+"/locks/live_broker_order_allowed",schemaPath:"#/$defs/locks/properties/live_broker_order_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err17];
}
else {
vErrors.push(err17);
}
errors++;
}
}
if(data2.profitability_claim_allowed !== undefined && func0.call(data2, "profitability_claim_allowed")){
if(false !== data2.profitability_claim_allowed){
const err18 = {instancePath:instancePath+"/locks/profitability_claim_allowed",schemaPath:"#/$defs/locks/properties/profitability_claim_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err18];
}
else {
vErrors.push(err18);
}
errors++;
}
}
if(data2.go_summary_allowed !== undefined && func0.call(data2, "go_summary_allowed")){
if(false !== data2.go_summary_allowed){
const err19 = {instancePath:instancePath+"/locks/go_summary_allowed",schemaPath:"#/$defs/locks/properties/go_summary_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err19];
}
else {
vErrors.push(err19);
}
errors++;
}
}
}
else {
const err20 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err20];
}
else {
vErrors.push(err20);
}
errors++;
}
}
if(data.cells !== undefined && func0.call(data, "cells")){
if(!(validate41(data.cells, {instancePath:instancePath+"/cells",parentData:data,parentDataProperty:"cells",rootData,dynamicAnchors}))){
vErrors = vErrors === null ? validate41.errors : vErrors.concat(validate41.errors);
errors = vErrors.length;
}
}
if(data.summary !== undefined && func0.call(data, "summary")){
let data10 = data.summary;
if(data10 && typeof data10 == "object" && !Array.isArray(data10)){
if((data10.total_cells === undefined) || (!(func0.call(data10, "total_cells")))){
const err21 = {instancePath:instancePath+"/summary",schemaPath:"#/$defs/matrixSummary/required",keyword:"required",params:{missingProperty: "total_cells"},message:"must have required property '"+"total_cells"+"'"};
if(vErrors === null){
vErrors = [err21];
}
else {
vErrors.push(err21);
}
errors++;
}
if((data10.pass_count === undefined) || (!(func0.call(data10, "pass_count")))){
const err22 = {instancePath:instancePath+"/summary",schemaPath:"#/$defs/matrixSummary/required",keyword:"required",params:{missingProperty: "pass_count"},message:"must have required property '"+"pass_count"+"'"};
if(vErrors === null){
vErrors = [err22];
}
else {
vErrors.push(err22);
}
errors++;
}
if((data10.fail_count === undefined) || (!(func0.call(data10, "fail_count")))){
const err23 = {instancePath:instancePath+"/summary",schemaPath:"#/$defs/matrixSummary/required",keyword:"required",params:{missingProperty: "fail_count"},message:"must have required property '"+"fail_count"+"'"};
if(vErrors === null){
vErrors = [err23];
}
else {
vErrors.push(err23);
}
errors++;
}
if((data10.blocked_count === undefined) || (!(func0.call(data10, "blocked_count")))){
const err24 = {instancePath:instancePath+"/summary",schemaPath:"#/$defs/matrixSummary/required",keyword:"required",params:{missingProperty: "blocked_count"},message:"must have required property '"+"blocked_count"+"'"};
if(vErrors === null){
vErrors = [err24];
}
else {
vErrors.push(err24);
}
errors++;
}
if((data10.pending_count === undefined) || (!(func0.call(data10, "pending_count")))){
const err25 = {instancePath:instancePath+"/summary",schemaPath:"#/$defs/matrixSummary/required",keyword:"required",params:{missingProperty: "pending_count"},message:"must have required property '"+"pending_count"+"'"};
if(vErrors === null){
vErrors = [err25];
}
else {
vErrors.push(err25);
}
errors++;
}
for(const key2 of Object.keys(data10)){
if(!(((((key2 === "total_cells") || (key2 === "pass_count")) || (key2 === "fail_count")) || (key2 === "blocked_count")) || (key2 === "pending_count"))){
const err26 = {instancePath:instancePath+"/summary",schemaPath:"#/$defs/matrixSummary/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key2},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err26];
}
else {
vErrors.push(err26);
}
errors++;
}
}
if(data10.total_cells !== undefined && func0.call(data10, "total_cells")){
if(50 !== data10.total_cells){
const err27 = {instancePath:instancePath+"/summary/total_cells",schemaPath:"#/$defs/matrixSummary/properties/total_cells/const",keyword:"const",params:{allowedValue: 50},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err27];
}
else {
vErrors.push(err27);
}
errors++;
}
}
if(data10.pass_count !== undefined && func0.call(data10, "pass_count")){
let data12 = data10.pass_count;
if(!(((typeof data12 == "number") && (!(data12 % 1) && !isNaN(data12))) && (isFinite(data12)))){
const err28 = {instancePath:instancePath+"/summary/pass_count",schemaPath:"#/$defs/matrixSummary/properties/pass_count/type",keyword:"type",params:{type: "integer"},message:"must be integer"};
if(vErrors === null){
vErrors = [err28];
}
else {
vErrors.push(err28);
}
errors++;
}
if((typeof data12 == "number") && (isFinite(data12))){
if(data12 < 0 || isNaN(data12)){
const err29 = {instancePath:instancePath+"/summary/pass_count",schemaPath:"#/$defs/matrixSummary/properties/pass_count/minimum",keyword:"minimum",params:{comparison: ">=", limit: 0},message:"must be >= 0"};
if(vErrors === null){
vErrors = [err29];
}
else {
vErrors.push(err29);
}
errors++;
}
}
}
if(data10.fail_count !== undefined && func0.call(data10, "fail_count")){
let data13 = data10.fail_count;
if(!(((typeof data13 == "number") && (!(data13 % 1) && !isNaN(data13))) && (isFinite(data13)))){
const err30 = {instancePath:instancePath+"/summary/fail_count",schemaPath:"#/$defs/matrixSummary/properties/fail_count/type",keyword:"type",params:{type: "integer"},message:"must be integer"};
if(vErrors === null){
vErrors = [err30];
}
else {
vErrors.push(err30);
}
errors++;
}
if((typeof data13 == "number") && (isFinite(data13))){
if(data13 < 0 || isNaN(data13)){
const err31 = {instancePath:instancePath+"/summary/fail_count",schemaPath:"#/$defs/matrixSummary/properties/fail_count/minimum",keyword:"minimum",params:{comparison: ">=", limit: 0},message:"must be >= 0"};
if(vErrors === null){
vErrors = [err31];
}
else {
vErrors.push(err31);
}
errors++;
}
}
}
if(data10.blocked_count !== undefined && func0.call(data10, "blocked_count")){
let data14 = data10.blocked_count;
if(!(((typeof data14 == "number") && (!(data14 % 1) && !isNaN(data14))) && (isFinite(data14)))){
const err32 = {instancePath:instancePath+"/summary/blocked_count",schemaPath:"#/$defs/matrixSummary/properties/blocked_count/type",keyword:"type",params:{type: "integer"},message:"must be integer"};
if(vErrors === null){
vErrors = [err32];
}
else {
vErrors.push(err32);
}
errors++;
}
if((typeof data14 == "number") && (isFinite(data14))){
if(data14 < 0 || isNaN(data14)){
const err33 = {instancePath:instancePath+"/summary/blocked_count",schemaPath:"#/$defs/matrixSummary/properties/blocked_count/minimum",keyword:"minimum",params:{comparison: ">=", limit: 0},message:"must be >= 0"};
if(vErrors === null){
vErrors = [err33];
}
else {
vErrors.push(err33);
}
errors++;
}
}
}
if(data10.pending_count !== undefined && func0.call(data10, "pending_count")){
let data15 = data10.pending_count;
if(!(((typeof data15 == "number") && (!(data15 % 1) && !isNaN(data15))) && (isFinite(data15)))){
const err34 = {instancePath:instancePath+"/summary/pending_count",schemaPath:"#/$defs/matrixSummary/properties/pending_count/type",keyword:"type",params:{type: "integer"},message:"must be integer"};
if(vErrors === null){
vErrors = [err34];
}
else {
vErrors.push(err34);
}
errors++;
}
if((typeof data15 == "number") && (isFinite(data15))){
if(data15 < 0 || isNaN(data15)){
const err35 = {instancePath:instancePath+"/summary/pending_count",schemaPath:"#/$defs/matrixSummary/properties/pending_count/minimum",keyword:"minimum",params:{comparison: ">=", limit: 0},message:"must be >= 0"};
if(vErrors === null){
vErrors = [err35];
}
else {
vErrors.push(err35);
}
errors++;
}
}
}
}
else {
const err36 = {instancePath:instancePath+"/summary",schemaPath:"#/$defs/matrixSummary/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err36];
}
else {
vErrors.push(err36);
}
errors++;
}
}
}
else {
const err37 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err37];
}
else {
vErrors.push(err37);
}
errors++;
}
validate83.errors = vErrors;
return errors === 0;
}
validate83.evaluated = {"props":true,"dynamicProps":false,"dynamicItems":false};

export const validateLedgerRoot = validate86;
const schema71 = {"type":"object","additionalProperties":false,"required":["route_id","source","list","locks"],"properties":{"route_id":{"const":"LEDGER"},"source":{"$ref":"#/$defs/source"},"locks":{"$ref":"#/$defs/locks"},"list":{"type":"object","additionalProperties":false,"required":["items","next_cursor"],"properties":{"items":{"type":"array","maxItems":100,"items":{"$ref":"#/$defs/ledgerEntry"}},"next_cursor":{"anyOf":[{"$ref":"#/$defs/cursor"},{"type":"null"}]}}}}};
const schema73 = {"type":"object","additionalProperties":false,"required":["entry_id","occurred_at","kind","amount","currency","source_sha256"],"properties":{"entry_id":{"$ref":"#/$defs/artifactId"},"occurred_at":{"$ref":"#/$defs/utc"},"kind":{"enum":["DEBIT","CREDIT","ADJUSTMENT"]},"amount":{"type":"number"},"currency":{"const":"KRONOS_CREDIT"},"source_sha256":{"$ref":"#/$defs/sha256"}}};

function validate46(data, {instancePath="", parentData, parentDataProperty, rootData=data, dynamicAnchors={}}={}){
let vErrors = null;
let errors = 0;
const evaluated0 = validate46.evaluated;
if(evaluated0.dynamicProps){
evaluated0.props = undefined;
}
if(evaluated0.dynamicItems){
evaluated0.items = undefined;
}
if(data && typeof data == "object" && !Array.isArray(data)){
if((data.entry_id === undefined) || (!(func0.call(data, "entry_id")))){
const err0 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "entry_id"},message:"must have required property '"+"entry_id"+"'"};
if(vErrors === null){
vErrors = [err0];
}
else {
vErrors.push(err0);
}
errors++;
}
if((data.occurred_at === undefined) || (!(func0.call(data, "occurred_at")))){
const err1 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "occurred_at"},message:"must have required property '"+"occurred_at"+"'"};
if(vErrors === null){
vErrors = [err1];
}
else {
vErrors.push(err1);
}
errors++;
}
if((data.kind === undefined) || (!(func0.call(data, "kind")))){
const err2 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "kind"},message:"must have required property '"+"kind"+"'"};
if(vErrors === null){
vErrors = [err2];
}
else {
vErrors.push(err2);
}
errors++;
}
if((data.amount === undefined) || (!(func0.call(data, "amount")))){
const err3 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "amount"},message:"must have required property '"+"amount"+"'"};
if(vErrors === null){
vErrors = [err3];
}
else {
vErrors.push(err3);
}
errors++;
}
if((data.currency === undefined) || (!(func0.call(data, "currency")))){
const err4 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "currency"},message:"must have required property '"+"currency"+"'"};
if(vErrors === null){
vErrors = [err4];
}
else {
vErrors.push(err4);
}
errors++;
}
if((data.source_sha256 === undefined) || (!(func0.call(data, "source_sha256")))){
const err5 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "source_sha256"},message:"must have required property '"+"source_sha256"+"'"};
if(vErrors === null){
vErrors = [err5];
}
else {
vErrors.push(err5);
}
errors++;
}
for(const key0 of Object.keys(data)){
if(!((((((key0 === "entry_id") || (key0 === "occurred_at")) || (key0 === "kind")) || (key0 === "amount")) || (key0 === "currency")) || (key0 === "source_sha256"))){
const err6 = {instancePath,schemaPath:"#/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key0},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err6];
}
else {
vErrors.push(err6);
}
errors++;
}
}
if(data.entry_id !== undefined && func0.call(data, "entry_id")){
let data0 = data.entry_id;
if(typeof data0 === "string"){
if(!pattern20.test(data0)){
const err7 = {instancePath:instancePath+"/entry_id",schemaPath:"#/$defs/artifactId/pattern",keyword:"pattern",params:{pattern: "^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"},message:"must match pattern \""+"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"+"\""};
if(vErrors === null){
vErrors = [err7];
}
else {
vErrors.push(err7);
}
errors++;
}
}
else {
const err8 = {instancePath:instancePath+"/entry_id",schemaPath:"#/$defs/artifactId/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err8];
}
else {
vErrors.push(err8);
}
errors++;
}
}
if(data.occurred_at !== undefined && func0.call(data, "occurred_at")){
let data1 = data.occurred_at;
if(typeof data1 === "string"){
if(!pattern5.test(data1)){
const err9 = {instancePath:instancePath+"/occurred_at",schemaPath:"#/$defs/utc/pattern",keyword:"pattern",params:{pattern: "^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"},message:"must match pattern \""+"^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"+"\""};
if(vErrors === null){
vErrors = [err9];
}
else {
vErrors.push(err9);
}
errors++;
}
if(!(formats0.validate(data1))){
const err10 = {instancePath:instancePath+"/occurred_at",schemaPath:"#/$defs/utc/format",keyword:"format",params:{format: "date-time"},message:"must match format \""+"date-time"+"\""};
if(vErrors === null){
vErrors = [err10];
}
else {
vErrors.push(err10);
}
errors++;
}
}
else {
const err11 = {instancePath:instancePath+"/occurred_at",schemaPath:"#/$defs/utc/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err11];
}
else {
vErrors.push(err11);
}
errors++;
}
}
if(data.kind !== undefined && func0.call(data, "kind")){
let data2 = data.kind;
if(!(((data2 === "DEBIT") || (data2 === "CREDIT")) || (data2 === "ADJUSTMENT"))){
const err12 = {instancePath:instancePath+"/kind",schemaPath:"#/properties/kind/enum",keyword:"enum",params:{allowedValues: schema73.properties.kind.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err12];
}
else {
vErrors.push(err12);
}
errors++;
}
}
if(data.amount !== undefined && func0.call(data, "amount")){
let data3 = data.amount;
if(!((typeof data3 == "number") && (isFinite(data3)))){
const err13 = {instancePath:instancePath+"/amount",schemaPath:"#/properties/amount/type",keyword:"type",params:{type: "number"},message:"must be number"};
if(vErrors === null){
vErrors = [err13];
}
else {
vErrors.push(err13);
}
errors++;
}
}
if(data.currency !== undefined && func0.call(data, "currency")){
if("KRONOS_CREDIT" !== data.currency){
const err14 = {instancePath:instancePath+"/currency",schemaPath:"#/properties/currency/const",keyword:"const",params:{allowedValue: "KRONOS_CREDIT"},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err14];
}
else {
vErrors.push(err14);
}
errors++;
}
}
if(data.source_sha256 !== undefined && func0.call(data, "source_sha256")){
let data5 = data.source_sha256;
if(typeof data5 === "string"){
if(!pattern4.test(data5)){
const err15 = {instancePath:instancePath+"/source_sha256",schemaPath:"#/$defs/sha256/pattern",keyword:"pattern",params:{pattern: "^[0-9a-f]{64}$"},message:"must match pattern \""+"^[0-9a-f]{64}$"+"\""};
if(vErrors === null){
vErrors = [err15];
}
else {
vErrors.push(err15);
}
errors++;
}
}
else {
const err16 = {instancePath:instancePath+"/source_sha256",schemaPath:"#/$defs/sha256/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err16];
}
else {
vErrors.push(err16);
}
errors++;
}
}
}
else {
const err17 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err17];
}
else {
vErrors.push(err17);
}
errors++;
}
validate46.errors = vErrors;
return errors === 0;
}
validate46.evaluated = {"props":true,"dynamicProps":false,"dynamicItems":false};


function validate86(data, {instancePath="", parentData, parentDataProperty, rootData=data, dynamicAnchors={}}={}){
let vErrors = null;
let errors = 0;
const evaluated0 = validate86.evaluated;
if(evaluated0.dynamicProps){
evaluated0.props = undefined;
}
if(evaluated0.dynamicItems){
evaluated0.items = undefined;
}
if(data && typeof data == "object" && !Array.isArray(data)){
if((data.route_id === undefined) || (!(func0.call(data, "route_id")))){
const err0 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "route_id"},message:"must have required property '"+"route_id"+"'"};
if(vErrors === null){
vErrors = [err0];
}
else {
vErrors.push(err0);
}
errors++;
}
if((data.source === undefined) || (!(func0.call(data, "source")))){
const err1 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "source"},message:"must have required property '"+"source"+"'"};
if(vErrors === null){
vErrors = [err1];
}
else {
vErrors.push(err1);
}
errors++;
}
if((data.list === undefined) || (!(func0.call(data, "list")))){
const err2 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "list"},message:"must have required property '"+"list"+"'"};
if(vErrors === null){
vErrors = [err2];
}
else {
vErrors.push(err2);
}
errors++;
}
if((data.locks === undefined) || (!(func0.call(data, "locks")))){
const err3 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "locks"},message:"must have required property '"+"locks"+"'"};
if(vErrors === null){
vErrors = [err3];
}
else {
vErrors.push(err3);
}
errors++;
}
for(const key0 of Object.keys(data)){
if(!((((key0 === "route_id") || (key0 === "source")) || (key0 === "locks")) || (key0 === "list"))){
const err4 = {instancePath,schemaPath:"#/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key0},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err4];
}
else {
vErrors.push(err4);
}
errors++;
}
}
if(data.route_id !== undefined && func0.call(data, "route_id")){
if("LEDGER" !== data.route_id){
const err5 = {instancePath:instancePath+"/route_id",schemaPath:"#/properties/route_id/const",keyword:"const",params:{allowedValue: "LEDGER"},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err5];
}
else {
vErrors.push(err5);
}
errors++;
}
}
if(data.source !== undefined && func0.call(data, "source")){
if(!(validate22(data.source, {instancePath:instancePath+"/source",parentData:data,parentDataProperty:"source",rootData,dynamicAnchors}))){
vErrors = vErrors === null ? validate22.errors : vErrors.concat(validate22.errors);
errors = vErrors.length;
}
}
if(data.locks !== undefined && func0.call(data, "locks")){
let data2 = data.locks;
if(data2 && typeof data2 == "object" && !Array.isArray(data2)){
if((data2.promotion_allowed === undefined) || (!(func0.call(data2, "promotion_allowed")))){
const err6 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "promotion_allowed"},message:"must have required property '"+"promotion_allowed"+"'"};
if(vErrors === null){
vErrors = [err6];
}
else {
vErrors.push(err6);
}
errors++;
}
if((data2.model_build_allowed === undefined) || (!(func0.call(data2, "model_build_allowed")))){
const err7 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "model_build_allowed"},message:"must have required property '"+"model_build_allowed"+"'"};
if(vErrors === null){
vErrors = [err7];
}
else {
vErrors.push(err7);
}
errors++;
}
if((data2.paper_forward_allowed === undefined) || (!(func0.call(data2, "paper_forward_allowed")))){
const err8 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "paper_forward_allowed"},message:"must have required property '"+"paper_forward_allowed"+"'"};
if(vErrors === null){
vErrors = [err8];
}
else {
vErrors.push(err8);
}
errors++;
}
if((data2.live_broker_order_allowed === undefined) || (!(func0.call(data2, "live_broker_order_allowed")))){
const err9 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "live_broker_order_allowed"},message:"must have required property '"+"live_broker_order_allowed"+"'"};
if(vErrors === null){
vErrors = [err9];
}
else {
vErrors.push(err9);
}
errors++;
}
if((data2.profitability_claim_allowed === undefined) || (!(func0.call(data2, "profitability_claim_allowed")))){
const err10 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "profitability_claim_allowed"},message:"must have required property '"+"profitability_claim_allowed"+"'"};
if(vErrors === null){
vErrors = [err10];
}
else {
vErrors.push(err10);
}
errors++;
}
if((data2.go_summary_allowed === undefined) || (!(func0.call(data2, "go_summary_allowed")))){
const err11 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "go_summary_allowed"},message:"must have required property '"+"go_summary_allowed"+"'"};
if(vErrors === null){
vErrors = [err11];
}
else {
vErrors.push(err11);
}
errors++;
}
for(const key1 of Object.keys(data2)){
if(!((((((key1 === "promotion_allowed") || (key1 === "model_build_allowed")) || (key1 === "paper_forward_allowed")) || (key1 === "live_broker_order_allowed")) || (key1 === "profitability_claim_allowed")) || (key1 === "go_summary_allowed"))){
const err12 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key1},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err12];
}
else {
vErrors.push(err12);
}
errors++;
}
}
if(data2.promotion_allowed !== undefined && func0.call(data2, "promotion_allowed")){
if(false !== data2.promotion_allowed){
const err13 = {instancePath:instancePath+"/locks/promotion_allowed",schemaPath:"#/$defs/locks/properties/promotion_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err13];
}
else {
vErrors.push(err13);
}
errors++;
}
}
if(data2.model_build_allowed !== undefined && func0.call(data2, "model_build_allowed")){
if(false !== data2.model_build_allowed){
const err14 = {instancePath:instancePath+"/locks/model_build_allowed",schemaPath:"#/$defs/locks/properties/model_build_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err14];
}
else {
vErrors.push(err14);
}
errors++;
}
}
if(data2.paper_forward_allowed !== undefined && func0.call(data2, "paper_forward_allowed")){
if(false !== data2.paper_forward_allowed){
const err15 = {instancePath:instancePath+"/locks/paper_forward_allowed",schemaPath:"#/$defs/locks/properties/paper_forward_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err15];
}
else {
vErrors.push(err15);
}
errors++;
}
}
if(data2.live_broker_order_allowed !== undefined && func0.call(data2, "live_broker_order_allowed")){
if(false !== data2.live_broker_order_allowed){
const err16 = {instancePath:instancePath+"/locks/live_broker_order_allowed",schemaPath:"#/$defs/locks/properties/live_broker_order_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err16];
}
else {
vErrors.push(err16);
}
errors++;
}
}
if(data2.profitability_claim_allowed !== undefined && func0.call(data2, "profitability_claim_allowed")){
if(false !== data2.profitability_claim_allowed){
const err17 = {instancePath:instancePath+"/locks/profitability_claim_allowed",schemaPath:"#/$defs/locks/properties/profitability_claim_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err17];
}
else {
vErrors.push(err17);
}
errors++;
}
}
if(data2.go_summary_allowed !== undefined && func0.call(data2, "go_summary_allowed")){
if(false !== data2.go_summary_allowed){
const err18 = {instancePath:instancePath+"/locks/go_summary_allowed",schemaPath:"#/$defs/locks/properties/go_summary_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err18];
}
else {
vErrors.push(err18);
}
errors++;
}
}
}
else {
const err19 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err19];
}
else {
vErrors.push(err19);
}
errors++;
}
}
if(data.list !== undefined && func0.call(data, "list")){
let data9 = data.list;
if(data9 && typeof data9 == "object" && !Array.isArray(data9)){
if((data9.items === undefined) || (!(func0.call(data9, "items")))){
const err20 = {instancePath:instancePath+"/list",schemaPath:"#/properties/list/required",keyword:"required",params:{missingProperty: "items"},message:"must have required property '"+"items"+"'"};
if(vErrors === null){
vErrors = [err20];
}
else {
vErrors.push(err20);
}
errors++;
}
if((data9.next_cursor === undefined) || (!(func0.call(data9, "next_cursor")))){
const err21 = {instancePath:instancePath+"/list",schemaPath:"#/properties/list/required",keyword:"required",params:{missingProperty: "next_cursor"},message:"must have required property '"+"next_cursor"+"'"};
if(vErrors === null){
vErrors = [err21];
}
else {
vErrors.push(err21);
}
errors++;
}
for(const key2 of Object.keys(data9)){
if(!((key2 === "items") || (key2 === "next_cursor"))){
const err22 = {instancePath:instancePath+"/list",schemaPath:"#/properties/list/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key2},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err22];
}
else {
vErrors.push(err22);
}
errors++;
}
}
if(data9.items !== undefined && func0.call(data9, "items")){
let data10 = data9.items;
if(Array.isArray(data10)){
if(data10.length > 100){
const err23 = {instancePath:instancePath+"/list/items",schemaPath:"#/properties/list/properties/items/maxItems",keyword:"maxItems",params:{limit: 100},message:"must NOT have more than 100 items"};
if(vErrors === null){
vErrors = [err23];
}
else {
vErrors.push(err23);
}
errors++;
}
const len0 = data10.length;
for(let i0=0; i0<len0; i0++){
if(!(validate46(data10[i0], {instancePath:instancePath+"/list/items/" + i0,parentData:data10,parentDataProperty:i0,rootData,dynamicAnchors}))){
vErrors = vErrors === null ? validate46.errors : vErrors.concat(validate46.errors);
errors = vErrors.length;
}
}
}
else {
const err24 = {instancePath:instancePath+"/list/items",schemaPath:"#/properties/list/properties/items/type",keyword:"type",params:{type: "array"},message:"must be array"};
if(vErrors === null){
vErrors = [err24];
}
else {
vErrors.push(err24);
}
errors++;
}
}
if(data9.next_cursor !== undefined && func0.call(data9, "next_cursor")){
let data12 = data9.next_cursor;
const _errs21 = errors;
let valid6 = false;
const _errs22 = errors;
if(typeof data12 === "string"){
if(func114(data12) > 2048){
const err25 = {instancePath:instancePath+"/list/next_cursor",schemaPath:"#/$defs/cursor/maxLength",keyword:"maxLength",params:{limit: 2048},message:"must NOT have more than 2048 characters"};
if(vErrors === null){
vErrors = [err25];
}
else {
vErrors.push(err25);
}
errors++;
}
if(func114(data12) < 16){
const err26 = {instancePath:instancePath+"/list/next_cursor",schemaPath:"#/$defs/cursor/minLength",keyword:"minLength",params:{limit: 16},message:"must NOT have fewer than 16 characters"};
if(vErrors === null){
vErrors = [err26];
}
else {
vErrors.push(err26);
}
errors++;
}
if(!pattern13.test(data12)){
const err27 = {instancePath:instancePath+"/list/next_cursor",schemaPath:"#/$defs/cursor/pattern",keyword:"pattern",params:{pattern: "^[A-Za-z0-9_-]+$"},message:"must match pattern \""+"^[A-Za-z0-9_-]+$"+"\""};
if(vErrors === null){
vErrors = [err27];
}
else {
vErrors.push(err27);
}
errors++;
}
}
else {
const err28 = {instancePath:instancePath+"/list/next_cursor",schemaPath:"#/$defs/cursor/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err28];
}
else {
vErrors.push(err28);
}
errors++;
}
var _valid0 = _errs22 === errors;
valid6 = valid6 || _valid0;
const _errs25 = errors;
if(data12 !== null){
const err29 = {instancePath:instancePath+"/list/next_cursor",schemaPath:"#/properties/list/properties/next_cursor/anyOf/1/type",keyword:"type",params:{type: "null"},message:"must be null"};
if(vErrors === null){
vErrors = [err29];
}
else {
vErrors.push(err29);
}
errors++;
}
var _valid0 = _errs25 === errors;
valid6 = valid6 || _valid0;
if(!valid6){
const err30 = {instancePath:instancePath+"/list/next_cursor",schemaPath:"#/properties/list/properties/next_cursor/anyOf",keyword:"anyOf",params:{},message:"must match a schema in anyOf"};
if(vErrors === null){
vErrors = [err30];
}
else {
vErrors.push(err30);
}
errors++;
}
else {
errors = _errs21;
if(vErrors !== null){
if(_errs21){
vErrors.length = _errs21;
}
else {
vErrors = null;
}
}
}
}
}
else {
const err31 = {instancePath:instancePath+"/list",schemaPath:"#/properties/list/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err31];
}
else {
vErrors.push(err31);
}
errors++;
}
}
}
else {
const err32 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err32];
}
else {
vErrors.push(err32);
}
errors++;
}
validate86.errors = vErrors;
return errors === 0;
}
validate86.evaluated = {"props":true,"dynamicProps":false,"dynamicItems":false};

export const validateArtifactsRoot = validate89;
const schema78 = {"type":"object","additionalProperties":false,"required":["route_id","source","list","locks"],"properties":{"route_id":{"const":"ARTIFACTS"},"source":{"$ref":"#/$defs/source"},"locks":{"$ref":"#/$defs/locks"},"list":{"type":"object","additionalProperties":false,"required":["items","next_cursor"],"properties":{"items":{"type":"array","maxItems":100,"items":{"$ref":"#/$defs/download"}},"next_cursor":{"anyOf":[{"$ref":"#/$defs/cursor"},{"type":"null"}]}}}}};
const schema80 = {"type":"object","additionalProperties":false,"required":["artifact","download_url","portable_filename"],"properties":{"artifact":{"$ref":"#/$defs/artifact"},"download_url":{"type":"string","pattern":"^/api/v5/rl/artifacts/[A-Za-z0-9][A-Za-z0-9_-]{0,127}/download(?:\\?run_id=[A-Za-z0-9][A-Za-z0-9._%~-]{0,383}&(?:revision|run_revision)=[1-9][0-9]{0,15})?$"},"portable_filename":{"type":"string","pattern":"^(?!(?:[Cc][Oo][Nn]|[Pp][Rr][Nn]|[Aa][Uu][Xx]|[Nn][Uu][Ll]|[Cc][Oo][Mm][1-9]|[Ll][Pp][Tt][1-9])\\.)[A-Za-z0-9][A-Za-z0-9_-]{0,126}\\.(?:json|csv|jsonl|md|png)$"},"run_id":{"$ref":"#/$defs/runId"},"run_revision":{"$ref":"#/$defs/runRevision"}}};
const schema81 = {"type":"object","additionalProperties":false,"x-kronos-extension-media-map":{"json":"application/json","csv":"text/csv","jsonl":"application/jsonl","md":"text/markdown","png":"image/png"},"required":["artifact_id","filename","media_type","byte_length","sha256","created_at"],"properties":{"artifact_id":{"$ref":"#/$defs/artifactId"},"filename":{"type":"string","pattern":"^(?!(?:[Cc][Oo][Nn]|[Pp][Rr][Nn]|[Aa][Uu][Xx]|[Nn][Uu][Ll]|[Cc][Oo][Mm][1-9]|[Ll][Pp][Tt][1-9])\\.)[A-Za-z0-9][A-Za-z0-9_-]{0,126}\\.(?:json|csv|jsonl|md|png)$"},"media_type":{"enum":["application/json","text/csv","application/jsonl","text/markdown","image/png"]},"byte_length":{"type":"integer","minimum":0,"maximum":26214400},"sha256":{"$ref":"#/$defs/sha256"},"created_at":{"$ref":"#/$defs/utc"}}};
const pattern30 = new RegExp("^(?!(?:[Cc][Oo][Nn]|[Pp][Rr][Nn]|[Aa][Uu][Xx]|[Nn][Uu][Ll]|[Cc][Oo][Mm][1-9]|[Ll][Pp][Tt][1-9])\\.)[A-Za-z0-9][A-Za-z0-9_-]{0,126}\\.(?:json|csv|jsonl|md|png)$", "u");

function validate52(data, {instancePath="", parentData, parentDataProperty, rootData=data, dynamicAnchors={}}={}){
let vErrors = null;
let errors = 0;
const evaluated0 = validate52.evaluated;
if(evaluated0.dynamicProps){
evaluated0.props = undefined;
}
if(evaluated0.dynamicItems){
evaluated0.items = undefined;
}
if(data && typeof data == "object" && !Array.isArray(data)){
if((data.artifact_id === undefined) || (!(func0.call(data, "artifact_id")))){
const err0 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "artifact_id"},message:"must have required property '"+"artifact_id"+"'"};
if(vErrors === null){
vErrors = [err0];
}
else {
vErrors.push(err0);
}
errors++;
}
if((data.filename === undefined) || (!(func0.call(data, "filename")))){
const err1 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "filename"},message:"must have required property '"+"filename"+"'"};
if(vErrors === null){
vErrors = [err1];
}
else {
vErrors.push(err1);
}
errors++;
}
if((data.media_type === undefined) || (!(func0.call(data, "media_type")))){
const err2 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "media_type"},message:"must have required property '"+"media_type"+"'"};
if(vErrors === null){
vErrors = [err2];
}
else {
vErrors.push(err2);
}
errors++;
}
if((data.byte_length === undefined) || (!(func0.call(data, "byte_length")))){
const err3 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "byte_length"},message:"must have required property '"+"byte_length"+"'"};
if(vErrors === null){
vErrors = [err3];
}
else {
vErrors.push(err3);
}
errors++;
}
if((data.sha256 === undefined) || (!(func0.call(data, "sha256")))){
const err4 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "sha256"},message:"must have required property '"+"sha256"+"'"};
if(vErrors === null){
vErrors = [err4];
}
else {
vErrors.push(err4);
}
errors++;
}
if((data.created_at === undefined) || (!(func0.call(data, "created_at")))){
const err5 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "created_at"},message:"must have required property '"+"created_at"+"'"};
if(vErrors === null){
vErrors = [err5];
}
else {
vErrors.push(err5);
}
errors++;
}
for(const key0 of Object.keys(data)){
if(!((((((key0 === "artifact_id") || (key0 === "filename")) || (key0 === "media_type")) || (key0 === "byte_length")) || (key0 === "sha256")) || (key0 === "created_at"))){
const err6 = {instancePath,schemaPath:"#/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key0},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err6];
}
else {
vErrors.push(err6);
}
errors++;
}
}
if(data.artifact_id !== undefined && func0.call(data, "artifact_id")){
let data0 = data.artifact_id;
if(typeof data0 === "string"){
if(!pattern20.test(data0)){
const err7 = {instancePath:instancePath+"/artifact_id",schemaPath:"#/$defs/artifactId/pattern",keyword:"pattern",params:{pattern: "^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"},message:"must match pattern \""+"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"+"\""};
if(vErrors === null){
vErrors = [err7];
}
else {
vErrors.push(err7);
}
errors++;
}
}
else {
const err8 = {instancePath:instancePath+"/artifact_id",schemaPath:"#/$defs/artifactId/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err8];
}
else {
vErrors.push(err8);
}
errors++;
}
}
if(data.filename !== undefined && func0.call(data, "filename")){
let data1 = data.filename;
if(typeof data1 === "string"){
if(!pattern30.test(data1)){
const err9 = {instancePath:instancePath+"/filename",schemaPath:"#/properties/filename/pattern",keyword:"pattern",params:{pattern: "^(?!(?:[Cc][Oo][Nn]|[Pp][Rr][Nn]|[Aa][Uu][Xx]|[Nn][Uu][Ll]|[Cc][Oo][Mm][1-9]|[Ll][Pp][Tt][1-9])\\.)[A-Za-z0-9][A-Za-z0-9_-]{0,126}\\.(?:json|csv|jsonl|md|png)$"},message:"must match pattern \""+"^(?!(?:[Cc][Oo][Nn]|[Pp][Rr][Nn]|[Aa][Uu][Xx]|[Nn][Uu][Ll]|[Cc][Oo][Mm][1-9]|[Ll][Pp][Tt][1-9])\\.)[A-Za-z0-9][A-Za-z0-9_-]{0,126}\\.(?:json|csv|jsonl|md|png)$"+"\""};
if(vErrors === null){
vErrors = [err9];
}
else {
vErrors.push(err9);
}
errors++;
}
}
else {
const err10 = {instancePath:instancePath+"/filename",schemaPath:"#/properties/filename/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err10];
}
else {
vErrors.push(err10);
}
errors++;
}
}
if(data.media_type !== undefined && func0.call(data, "media_type")){
let data2 = data.media_type;
if(!(((((data2 === "application/json") || (data2 === "text/csv")) || (data2 === "application/jsonl")) || (data2 === "text/markdown")) || (data2 === "image/png"))){
const err11 = {instancePath:instancePath+"/media_type",schemaPath:"#/properties/media_type/enum",keyword:"enum",params:{allowedValues: schema81.properties.media_type.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err11];
}
else {
vErrors.push(err11);
}
errors++;
}
}
if(data.byte_length !== undefined && func0.call(data, "byte_length")){
let data3 = data.byte_length;
if(!(((typeof data3 == "number") && (!(data3 % 1) && !isNaN(data3))) && (isFinite(data3)))){
const err12 = {instancePath:instancePath+"/byte_length",schemaPath:"#/properties/byte_length/type",keyword:"type",params:{type: "integer"},message:"must be integer"};
if(vErrors === null){
vErrors = [err12];
}
else {
vErrors.push(err12);
}
errors++;
}
if((typeof data3 == "number") && (isFinite(data3))){
if(data3 > 26214400 || isNaN(data3)){
const err13 = {instancePath:instancePath+"/byte_length",schemaPath:"#/properties/byte_length/maximum",keyword:"maximum",params:{comparison: "<=", limit: 26214400},message:"must be <= 26214400"};
if(vErrors === null){
vErrors = [err13];
}
else {
vErrors.push(err13);
}
errors++;
}
if(data3 < 0 || isNaN(data3)){
const err14 = {instancePath:instancePath+"/byte_length",schemaPath:"#/properties/byte_length/minimum",keyword:"minimum",params:{comparison: ">=", limit: 0},message:"must be >= 0"};
if(vErrors === null){
vErrors = [err14];
}
else {
vErrors.push(err14);
}
errors++;
}
}
}
if(data.sha256 !== undefined && func0.call(data, "sha256")){
let data4 = data.sha256;
if(typeof data4 === "string"){
if(!pattern4.test(data4)){
const err15 = {instancePath:instancePath+"/sha256",schemaPath:"#/$defs/sha256/pattern",keyword:"pattern",params:{pattern: "^[0-9a-f]{64}$"},message:"must match pattern \""+"^[0-9a-f]{64}$"+"\""};
if(vErrors === null){
vErrors = [err15];
}
else {
vErrors.push(err15);
}
errors++;
}
}
else {
const err16 = {instancePath:instancePath+"/sha256",schemaPath:"#/$defs/sha256/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err16];
}
else {
vErrors.push(err16);
}
errors++;
}
}
if(data.created_at !== undefined && func0.call(data, "created_at")){
let data5 = data.created_at;
if(typeof data5 === "string"){
if(!pattern5.test(data5)){
const err17 = {instancePath:instancePath+"/created_at",schemaPath:"#/$defs/utc/pattern",keyword:"pattern",params:{pattern: "^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"},message:"must match pattern \""+"^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"+"\""};
if(vErrors === null){
vErrors = [err17];
}
else {
vErrors.push(err17);
}
errors++;
}
if(!(formats0.validate(data5))){
const err18 = {instancePath:instancePath+"/created_at",schemaPath:"#/$defs/utc/format",keyword:"format",params:{format: "date-time"},message:"must match format \""+"date-time"+"\""};
if(vErrors === null){
vErrors = [err18];
}
else {
vErrors.push(err18);
}
errors++;
}
}
else {
const err19 = {instancePath:instancePath+"/created_at",schemaPath:"#/$defs/utc/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err19];
}
else {
vErrors.push(err19);
}
errors++;
}
}
}
else {
const err20 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err20];
}
else {
vErrors.push(err20);
}
errors++;
}
validate52.errors = vErrors;
return errors === 0;
}
validate52.evaluated = {"props":true,"dynamicProps":false,"dynamicItems":false};

const pattern33 = new RegExp("^/api/v5/rl/artifacts/[A-Za-z0-9][A-Za-z0-9_-]{0,127}/download(?:\\?run_id=[A-Za-z0-9][A-Za-z0-9._%~-]{0,383}&(?:revision|run_revision)=[1-9][0-9]{0,15})?$", "u");

function validate51(data, {instancePath="", parentData, parentDataProperty, rootData=data, dynamicAnchors={}}={}){
let vErrors = null;
let errors = 0;
const evaluated0 = validate51.evaluated;
if(evaluated0.dynamicProps){
evaluated0.props = undefined;
}
if(evaluated0.dynamicItems){
evaluated0.items = undefined;
}
if(data && typeof data == "object" && !Array.isArray(data)){
if((data.artifact === undefined) || (!(func0.call(data, "artifact")))){
const err0 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "artifact"},message:"must have required property '"+"artifact"+"'"};
if(vErrors === null){
vErrors = [err0];
}
else {
vErrors.push(err0);
}
errors++;
}
if((data.download_url === undefined) || (!(func0.call(data, "download_url")))){
const err1 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "download_url"},message:"must have required property '"+"download_url"+"'"};
if(vErrors === null){
vErrors = [err1];
}
else {
vErrors.push(err1);
}
errors++;
}
if((data.portable_filename === undefined) || (!(func0.call(data, "portable_filename")))){
const err2 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "portable_filename"},message:"must have required property '"+"portable_filename"+"'"};
if(vErrors === null){
vErrors = [err2];
}
else {
vErrors.push(err2);
}
errors++;
}
for(const key0 of Object.keys(data)){
if(!(((((key0 === "artifact") || (key0 === "download_url")) || (key0 === "portable_filename")) || (key0 === "run_id")) || (key0 === "run_revision"))){
const err3 = {instancePath,schemaPath:"#/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key0},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err3];
}
else {
vErrors.push(err3);
}
errors++;
}
}
if(data.artifact !== undefined && func0.call(data, "artifact")){
if(!(validate52(data.artifact, {instancePath:instancePath+"/artifact",parentData:data,parentDataProperty:"artifact",rootData,dynamicAnchors}))){
vErrors = vErrors === null ? validate52.errors : vErrors.concat(validate52.errors);
errors = vErrors.length;
}
}
if(data.download_url !== undefined && func0.call(data, "download_url")){
let data1 = data.download_url;
if(typeof data1 === "string"){
if(!pattern33.test(data1)){
const err4 = {instancePath:instancePath+"/download_url",schemaPath:"#/properties/download_url/pattern",keyword:"pattern",params:{pattern: "^/api/v5/rl/artifacts/[A-Za-z0-9][A-Za-z0-9_-]{0,127}/download(?:\\?run_id=[A-Za-z0-9][A-Za-z0-9._%~-]{0,383}&(?:revision|run_revision)=[1-9][0-9]{0,15})?$"},message:"must match pattern \""+"^/api/v5/rl/artifacts/[A-Za-z0-9][A-Za-z0-9_-]{0,127}/download(?:\\?run_id=[A-Za-z0-9][A-Za-z0-9._%~-]{0,383}&(?:revision|run_revision)=[1-9][0-9]{0,15})?$"+"\""};
if(vErrors === null){
vErrors = [err4];
}
else {
vErrors.push(err4);
}
errors++;
}
}
else {
const err5 = {instancePath:instancePath+"/download_url",schemaPath:"#/properties/download_url/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err5];
}
else {
vErrors.push(err5);
}
errors++;
}
}
if(data.portable_filename !== undefined && func0.call(data, "portable_filename")){
let data2 = data.portable_filename;
if(typeof data2 === "string"){
if(!pattern30.test(data2)){
const err6 = {instancePath:instancePath+"/portable_filename",schemaPath:"#/properties/portable_filename/pattern",keyword:"pattern",params:{pattern: "^(?!(?:[Cc][Oo][Nn]|[Pp][Rr][Nn]|[Aa][Uu][Xx]|[Nn][Uu][Ll]|[Cc][Oo][Mm][1-9]|[Ll][Pp][Tt][1-9])\\.)[A-Za-z0-9][A-Za-z0-9_-]{0,126}\\.(?:json|csv|jsonl|md|png)$"},message:"must match pattern \""+"^(?!(?:[Cc][Oo][Nn]|[Pp][Rr][Nn]|[Aa][Uu][Xx]|[Nn][Uu][Ll]|[Cc][Oo][Mm][1-9]|[Ll][Pp][Tt][1-9])\\.)[A-Za-z0-9][A-Za-z0-9_-]{0,126}\\.(?:json|csv|jsonl|md|png)$"+"\""};
if(vErrors === null){
vErrors = [err6];
}
else {
vErrors.push(err6);
}
errors++;
}
}
else {
const err7 = {instancePath:instancePath+"/portable_filename",schemaPath:"#/properties/portable_filename/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err7];
}
else {
vErrors.push(err7);
}
errors++;
}
}
if(data.run_id !== undefined && func0.call(data, "run_id")){
let data3 = data.run_id;
if(typeof data3 === "string"){
if(!pattern6.test(data3)){
const err8 = {instancePath:instancePath+"/run_id",schemaPath:"#/$defs/runId/pattern",keyword:"pattern",params:{pattern: "^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"},message:"must match pattern \""+"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"+"\""};
if(vErrors === null){
vErrors = [err8];
}
else {
vErrors.push(err8);
}
errors++;
}
}
else {
const err9 = {instancePath:instancePath+"/run_id",schemaPath:"#/$defs/runId/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err9];
}
else {
vErrors.push(err9);
}
errors++;
}
}
if(data.run_revision !== undefined && func0.call(data, "run_revision")){
let data4 = data.run_revision;
if(!(((typeof data4 == "number") && (!(data4 % 1) && !isNaN(data4))) && (isFinite(data4)))){
const err10 = {instancePath:instancePath+"/run_revision",schemaPath:"#/$defs/runRevision/type",keyword:"type",params:{type: "integer"},message:"must be integer"};
if(vErrors === null){
vErrors = [err10];
}
else {
vErrors.push(err10);
}
errors++;
}
if((typeof data4 == "number") && (isFinite(data4))){
if(data4 > 9007199254740991 || isNaN(data4)){
const err11 = {instancePath:instancePath+"/run_revision",schemaPath:"#/$defs/runRevision/maximum",keyword:"maximum",params:{comparison: "<=", limit: 9007199254740991},message:"must be <= 9007199254740991"};
if(vErrors === null){
vErrors = [err11];
}
else {
vErrors.push(err11);
}
errors++;
}
if(data4 < 1 || isNaN(data4)){
const err12 = {instancePath:instancePath+"/run_revision",schemaPath:"#/$defs/runRevision/minimum",keyword:"minimum",params:{comparison: ">=", limit: 1},message:"must be >= 1"};
if(vErrors === null){
vErrors = [err12];
}
else {
vErrors.push(err12);
}
errors++;
}
}
}
}
else {
const err13 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err13];
}
else {
vErrors.push(err13);
}
errors++;
}
validate51.errors = vErrors;
return errors === 0;
}
validate51.evaluated = {"props":true,"dynamicProps":false,"dynamicItems":false};


function validate89(data, {instancePath="", parentData, parentDataProperty, rootData=data, dynamicAnchors={}}={}){
let vErrors = null;
let errors = 0;
const evaluated0 = validate89.evaluated;
if(evaluated0.dynamicProps){
evaluated0.props = undefined;
}
if(evaluated0.dynamicItems){
evaluated0.items = undefined;
}
if(data && typeof data == "object" && !Array.isArray(data)){
if((data.route_id === undefined) || (!(func0.call(data, "route_id")))){
const err0 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "route_id"},message:"must have required property '"+"route_id"+"'"};
if(vErrors === null){
vErrors = [err0];
}
else {
vErrors.push(err0);
}
errors++;
}
if((data.source === undefined) || (!(func0.call(data, "source")))){
const err1 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "source"},message:"must have required property '"+"source"+"'"};
if(vErrors === null){
vErrors = [err1];
}
else {
vErrors.push(err1);
}
errors++;
}
if((data.list === undefined) || (!(func0.call(data, "list")))){
const err2 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "list"},message:"must have required property '"+"list"+"'"};
if(vErrors === null){
vErrors = [err2];
}
else {
vErrors.push(err2);
}
errors++;
}
if((data.locks === undefined) || (!(func0.call(data, "locks")))){
const err3 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "locks"},message:"must have required property '"+"locks"+"'"};
if(vErrors === null){
vErrors = [err3];
}
else {
vErrors.push(err3);
}
errors++;
}
for(const key0 of Object.keys(data)){
if(!((((key0 === "route_id") || (key0 === "source")) || (key0 === "locks")) || (key0 === "list"))){
const err4 = {instancePath,schemaPath:"#/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key0},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err4];
}
else {
vErrors.push(err4);
}
errors++;
}
}
if(data.route_id !== undefined && func0.call(data, "route_id")){
if("ARTIFACTS" !== data.route_id){
const err5 = {instancePath:instancePath+"/route_id",schemaPath:"#/properties/route_id/const",keyword:"const",params:{allowedValue: "ARTIFACTS"},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err5];
}
else {
vErrors.push(err5);
}
errors++;
}
}
if(data.source !== undefined && func0.call(data, "source")){
if(!(validate22(data.source, {instancePath:instancePath+"/source",parentData:data,parentDataProperty:"source",rootData,dynamicAnchors}))){
vErrors = vErrors === null ? validate22.errors : vErrors.concat(validate22.errors);
errors = vErrors.length;
}
}
if(data.locks !== undefined && func0.call(data, "locks")){
let data2 = data.locks;
if(data2 && typeof data2 == "object" && !Array.isArray(data2)){
if((data2.promotion_allowed === undefined) || (!(func0.call(data2, "promotion_allowed")))){
const err6 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "promotion_allowed"},message:"must have required property '"+"promotion_allowed"+"'"};
if(vErrors === null){
vErrors = [err6];
}
else {
vErrors.push(err6);
}
errors++;
}
if((data2.model_build_allowed === undefined) || (!(func0.call(data2, "model_build_allowed")))){
const err7 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "model_build_allowed"},message:"must have required property '"+"model_build_allowed"+"'"};
if(vErrors === null){
vErrors = [err7];
}
else {
vErrors.push(err7);
}
errors++;
}
if((data2.paper_forward_allowed === undefined) || (!(func0.call(data2, "paper_forward_allowed")))){
const err8 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "paper_forward_allowed"},message:"must have required property '"+"paper_forward_allowed"+"'"};
if(vErrors === null){
vErrors = [err8];
}
else {
vErrors.push(err8);
}
errors++;
}
if((data2.live_broker_order_allowed === undefined) || (!(func0.call(data2, "live_broker_order_allowed")))){
const err9 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "live_broker_order_allowed"},message:"must have required property '"+"live_broker_order_allowed"+"'"};
if(vErrors === null){
vErrors = [err9];
}
else {
vErrors.push(err9);
}
errors++;
}
if((data2.profitability_claim_allowed === undefined) || (!(func0.call(data2, "profitability_claim_allowed")))){
const err10 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "profitability_claim_allowed"},message:"must have required property '"+"profitability_claim_allowed"+"'"};
if(vErrors === null){
vErrors = [err10];
}
else {
vErrors.push(err10);
}
errors++;
}
if((data2.go_summary_allowed === undefined) || (!(func0.call(data2, "go_summary_allowed")))){
const err11 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "go_summary_allowed"},message:"must have required property '"+"go_summary_allowed"+"'"};
if(vErrors === null){
vErrors = [err11];
}
else {
vErrors.push(err11);
}
errors++;
}
for(const key1 of Object.keys(data2)){
if(!((((((key1 === "promotion_allowed") || (key1 === "model_build_allowed")) || (key1 === "paper_forward_allowed")) || (key1 === "live_broker_order_allowed")) || (key1 === "profitability_claim_allowed")) || (key1 === "go_summary_allowed"))){
const err12 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key1},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err12];
}
else {
vErrors.push(err12);
}
errors++;
}
}
if(data2.promotion_allowed !== undefined && func0.call(data2, "promotion_allowed")){
if(false !== data2.promotion_allowed){
const err13 = {instancePath:instancePath+"/locks/promotion_allowed",schemaPath:"#/$defs/locks/properties/promotion_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err13];
}
else {
vErrors.push(err13);
}
errors++;
}
}
if(data2.model_build_allowed !== undefined && func0.call(data2, "model_build_allowed")){
if(false !== data2.model_build_allowed){
const err14 = {instancePath:instancePath+"/locks/model_build_allowed",schemaPath:"#/$defs/locks/properties/model_build_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err14];
}
else {
vErrors.push(err14);
}
errors++;
}
}
if(data2.paper_forward_allowed !== undefined && func0.call(data2, "paper_forward_allowed")){
if(false !== data2.paper_forward_allowed){
const err15 = {instancePath:instancePath+"/locks/paper_forward_allowed",schemaPath:"#/$defs/locks/properties/paper_forward_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err15];
}
else {
vErrors.push(err15);
}
errors++;
}
}
if(data2.live_broker_order_allowed !== undefined && func0.call(data2, "live_broker_order_allowed")){
if(false !== data2.live_broker_order_allowed){
const err16 = {instancePath:instancePath+"/locks/live_broker_order_allowed",schemaPath:"#/$defs/locks/properties/live_broker_order_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err16];
}
else {
vErrors.push(err16);
}
errors++;
}
}
if(data2.profitability_claim_allowed !== undefined && func0.call(data2, "profitability_claim_allowed")){
if(false !== data2.profitability_claim_allowed){
const err17 = {instancePath:instancePath+"/locks/profitability_claim_allowed",schemaPath:"#/$defs/locks/properties/profitability_claim_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err17];
}
else {
vErrors.push(err17);
}
errors++;
}
}
if(data2.go_summary_allowed !== undefined && func0.call(data2, "go_summary_allowed")){
if(false !== data2.go_summary_allowed){
const err18 = {instancePath:instancePath+"/locks/go_summary_allowed",schemaPath:"#/$defs/locks/properties/go_summary_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err18];
}
else {
vErrors.push(err18);
}
errors++;
}
}
}
else {
const err19 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err19];
}
else {
vErrors.push(err19);
}
errors++;
}
}
if(data.list !== undefined && func0.call(data, "list")){
let data9 = data.list;
if(data9 && typeof data9 == "object" && !Array.isArray(data9)){
if((data9.items === undefined) || (!(func0.call(data9, "items")))){
const err20 = {instancePath:instancePath+"/list",schemaPath:"#/properties/list/required",keyword:"required",params:{missingProperty: "items"},message:"must have required property '"+"items"+"'"};
if(vErrors === null){
vErrors = [err20];
}
else {
vErrors.push(err20);
}
errors++;
}
if((data9.next_cursor === undefined) || (!(func0.call(data9, "next_cursor")))){
const err21 = {instancePath:instancePath+"/list",schemaPath:"#/properties/list/required",keyword:"required",params:{missingProperty: "next_cursor"},message:"must have required property '"+"next_cursor"+"'"};
if(vErrors === null){
vErrors = [err21];
}
else {
vErrors.push(err21);
}
errors++;
}
for(const key2 of Object.keys(data9)){
if(!((key2 === "items") || (key2 === "next_cursor"))){
const err22 = {instancePath:instancePath+"/list",schemaPath:"#/properties/list/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key2},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err22];
}
else {
vErrors.push(err22);
}
errors++;
}
}
if(data9.items !== undefined && func0.call(data9, "items")){
let data10 = data9.items;
if(Array.isArray(data10)){
if(data10.length > 100){
const err23 = {instancePath:instancePath+"/list/items",schemaPath:"#/properties/list/properties/items/maxItems",keyword:"maxItems",params:{limit: 100},message:"must NOT have more than 100 items"};
if(vErrors === null){
vErrors = [err23];
}
else {
vErrors.push(err23);
}
errors++;
}
const len0 = data10.length;
for(let i0=0; i0<len0; i0++){
if(!(validate51(data10[i0], {instancePath:instancePath+"/list/items/" + i0,parentData:data10,parentDataProperty:i0,rootData,dynamicAnchors}))){
vErrors = vErrors === null ? validate51.errors : vErrors.concat(validate51.errors);
errors = vErrors.length;
}
}
}
else {
const err24 = {instancePath:instancePath+"/list/items",schemaPath:"#/properties/list/properties/items/type",keyword:"type",params:{type: "array"},message:"must be array"};
if(vErrors === null){
vErrors = [err24];
}
else {
vErrors.push(err24);
}
errors++;
}
}
if(data9.next_cursor !== undefined && func0.call(data9, "next_cursor")){
let data12 = data9.next_cursor;
const _errs21 = errors;
let valid6 = false;
const _errs22 = errors;
if(typeof data12 === "string"){
if(func114(data12) > 2048){
const err25 = {instancePath:instancePath+"/list/next_cursor",schemaPath:"#/$defs/cursor/maxLength",keyword:"maxLength",params:{limit: 2048},message:"must NOT have more than 2048 characters"};
if(vErrors === null){
vErrors = [err25];
}
else {
vErrors.push(err25);
}
errors++;
}
if(func114(data12) < 16){
const err26 = {instancePath:instancePath+"/list/next_cursor",schemaPath:"#/$defs/cursor/minLength",keyword:"minLength",params:{limit: 16},message:"must NOT have fewer than 16 characters"};
if(vErrors === null){
vErrors = [err26];
}
else {
vErrors.push(err26);
}
errors++;
}
if(!pattern13.test(data12)){
const err27 = {instancePath:instancePath+"/list/next_cursor",schemaPath:"#/$defs/cursor/pattern",keyword:"pattern",params:{pattern: "^[A-Za-z0-9_-]+$"},message:"must match pattern \""+"^[A-Za-z0-9_-]+$"+"\""};
if(vErrors === null){
vErrors = [err27];
}
else {
vErrors.push(err27);
}
errors++;
}
}
else {
const err28 = {instancePath:instancePath+"/list/next_cursor",schemaPath:"#/$defs/cursor/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err28];
}
else {
vErrors.push(err28);
}
errors++;
}
var _valid0 = _errs22 === errors;
valid6 = valid6 || _valid0;
const _errs25 = errors;
if(data12 !== null){
const err29 = {instancePath:instancePath+"/list/next_cursor",schemaPath:"#/properties/list/properties/next_cursor/anyOf/1/type",keyword:"type",params:{type: "null"},message:"must be null"};
if(vErrors === null){
vErrors = [err29];
}
else {
vErrors.push(err29);
}
errors++;
}
var _valid0 = _errs25 === errors;
valid6 = valid6 || _valid0;
if(!valid6){
const err30 = {instancePath:instancePath+"/list/next_cursor",schemaPath:"#/properties/list/properties/next_cursor/anyOf",keyword:"anyOf",params:{},message:"must match a schema in anyOf"};
if(vErrors === null){
vErrors = [err30];
}
else {
vErrors.push(err30);
}
errors++;
}
else {
errors = _errs21;
if(vErrors !== null){
if(_errs21){
vErrors.length = _errs21;
}
else {
vErrors = null;
}
}
}
}
}
else {
const err31 = {instancePath:instancePath+"/list",schemaPath:"#/properties/list/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err31];
}
else {
vErrors.push(err31);
}
errors++;
}
}
}
else {
const err32 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err32];
}
else {
vErrors.push(err32);
}
errors++;
}
validate89.errors = vErrors;
return errors === 0;
}
validate89.evaluated = {"props":true,"dynamicProps":false,"dynamicItems":false};

export const validateD0Root = validate92;
const schema88 = {"type":"object","additionalProperties":false,"required":["route_id","source","d0","locks"],"properties":{"route_id":{"const":"D0"},"source":{"$ref":"#/$defs/source"},"d0":{"$ref":"#/$defs/d0"},"locks":{"$ref":"#/$defs/locks"}}};
const schema89 = {"type":"object","additionalProperties":false,"required":["status","price_basis","source_sha256","updated_at"],"properties":{"status":{"enum":["PASS","FAIL","BLOCKED","PENDING"]},"price_basis":{"enum":["ADJUSTED","RAW","UNKNOWN"]},"source_sha256":{"$ref":"#/$defs/sha256"},"updated_at":{"$ref":"#/$defs/utc"}},"allOf":[{"if":{"properties":{"status":{"const":"PASS"}}},"then":{"properties":{"price_basis":{"enum":["RAW","ADJUSTED"]}}}},{"if":{"properties":{"price_basis":{"const":"UNKNOWN"}}},"then":{"properties":{"status":{"enum":["BLOCKED","PENDING"]}}}}]};

function validate58(data, {instancePath="", parentData, parentDataProperty, rootData=data, dynamicAnchors={}}={}){
let vErrors = null;
let errors = 0;
const evaluated0 = validate58.evaluated;
if(evaluated0.dynamicProps){
evaluated0.props = undefined;
}
if(evaluated0.dynamicItems){
evaluated0.items = undefined;
}
const _errs2 = errors;
let valid1 = true;
const _errs3 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
if(data.status !== undefined && func0.call(data, "status")){
if("PASS" !== data.status){
const err0 = {};
if(vErrors === null){
vErrors = [err0];
}
else {
vErrors.push(err0);
}
errors++;
}
}
}
var _valid0 = _errs3 === errors;
errors = _errs2;
if(vErrors !== null){
if(_errs2){
vErrors.length = _errs2;
}
else {
vErrors = null;
}
}
if(_valid0){
const _errs5 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
if(data.price_basis !== undefined && func0.call(data, "price_basis")){
let data1 = data.price_basis;
if(!((data1 === "RAW") || (data1 === "ADJUSTED"))){
const err1 = {instancePath:instancePath+"/price_basis",schemaPath:"#/allOf/0/then/properties/price_basis/enum",keyword:"enum",params:{allowedValues: schema89.allOf[0].then.properties.price_basis.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err1];
}
else {
vErrors.push(err1);
}
errors++;
}
}
}
var _valid0 = _errs5 === errors;
valid1 = _valid0;
if(valid1){
var props0 = {};
props0.price_basis = true;
props0.status = true;
}
}
if(!valid1){
const err2 = {instancePath,schemaPath:"#/allOf/0/if",keyword:"if",params:{failingKeyword: "then"},message:"must match \"then\" schema"};
if(vErrors === null){
vErrors = [err2];
}
else {
vErrors.push(err2);
}
errors++;
}
const _errs8 = errors;
let valid4 = true;
const _errs9 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
if(data.price_basis !== undefined && func0.call(data, "price_basis")){
if("UNKNOWN" !== data.price_basis){
const err3 = {};
if(vErrors === null){
vErrors = [err3];
}
else {
vErrors.push(err3);
}
errors++;
}
}
}
var _valid1 = _errs9 === errors;
errors = _errs8;
if(vErrors !== null){
if(_errs8){
vErrors.length = _errs8;
}
else {
vErrors = null;
}
}
if(_valid1){
const _errs11 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
if(data.status !== undefined && func0.call(data, "status")){
let data3 = data.status;
if(!((data3 === "BLOCKED") || (data3 === "PENDING"))){
const err4 = {instancePath:instancePath+"/status",schemaPath:"#/allOf/1/then/properties/status/enum",keyword:"enum",params:{allowedValues: schema89.allOf[1].then.properties.status.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err4];
}
else {
vErrors.push(err4);
}
errors++;
}
}
}
var _valid1 = _errs11 === errors;
valid4 = _valid1;
if(valid4){
var props1 = {};
props1.status = true;
props1.price_basis = true;
}
}
if(!valid4){
const err5 = {instancePath,schemaPath:"#/allOf/1/if",keyword:"if",params:{failingKeyword: "then"},message:"must match \"then\" schema"};
if(vErrors === null){
vErrors = [err5];
}
else {
vErrors.push(err5);
}
errors++;
}
if(props0 !== true && props1 !== undefined){
if(props1 === true){
props0 = true;
}
else {
props0 = props0 || {};
Object.assign(props0, props1);
}
}
if(data && typeof data == "object" && !Array.isArray(data)){
if((data.status === undefined) || (!(func0.call(data, "status")))){
const err6 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "status"},message:"must have required property '"+"status"+"'"};
if(vErrors === null){
vErrors = [err6];
}
else {
vErrors.push(err6);
}
errors++;
}
if((data.price_basis === undefined) || (!(func0.call(data, "price_basis")))){
const err7 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "price_basis"},message:"must have required property '"+"price_basis"+"'"};
if(vErrors === null){
vErrors = [err7];
}
else {
vErrors.push(err7);
}
errors++;
}
if((data.source_sha256 === undefined) || (!(func0.call(data, "source_sha256")))){
const err8 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "source_sha256"},message:"must have required property '"+"source_sha256"+"'"};
if(vErrors === null){
vErrors = [err8];
}
else {
vErrors.push(err8);
}
errors++;
}
if((data.updated_at === undefined) || (!(func0.call(data, "updated_at")))){
const err9 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "updated_at"},message:"must have required property '"+"updated_at"+"'"};
if(vErrors === null){
vErrors = [err9];
}
else {
vErrors.push(err9);
}
errors++;
}
for(const key0 of Object.keys(data)){
if(!((((key0 === "status") || (key0 === "price_basis")) || (key0 === "source_sha256")) || (key0 === "updated_at"))){
const err10 = {instancePath,schemaPath:"#/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key0},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err10];
}
else {
vErrors.push(err10);
}
errors++;
}
}
if(data.status !== undefined && func0.call(data, "status")){
let data4 = data.status;
if(!((((data4 === "PASS") || (data4 === "FAIL")) || (data4 === "BLOCKED")) || (data4 === "PENDING"))){
const err11 = {instancePath:instancePath+"/status",schemaPath:"#/properties/status/enum",keyword:"enum",params:{allowedValues: schema89.properties.status.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err11];
}
else {
vErrors.push(err11);
}
errors++;
}
}
if(data.price_basis !== undefined && func0.call(data, "price_basis")){
let data5 = data.price_basis;
if(!(((data5 === "ADJUSTED") || (data5 === "RAW")) || (data5 === "UNKNOWN"))){
const err12 = {instancePath:instancePath+"/price_basis",schemaPath:"#/properties/price_basis/enum",keyword:"enum",params:{allowedValues: schema89.properties.price_basis.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err12];
}
else {
vErrors.push(err12);
}
errors++;
}
}
if(data.source_sha256 !== undefined && func0.call(data, "source_sha256")){
let data6 = data.source_sha256;
if(typeof data6 === "string"){
if(!pattern4.test(data6)){
const err13 = {instancePath:instancePath+"/source_sha256",schemaPath:"#/$defs/sha256/pattern",keyword:"pattern",params:{pattern: "^[0-9a-f]{64}$"},message:"must match pattern \""+"^[0-9a-f]{64}$"+"\""};
if(vErrors === null){
vErrors = [err13];
}
else {
vErrors.push(err13);
}
errors++;
}
}
else {
const err14 = {instancePath:instancePath+"/source_sha256",schemaPath:"#/$defs/sha256/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err14];
}
else {
vErrors.push(err14);
}
errors++;
}
}
if(data.updated_at !== undefined && func0.call(data, "updated_at")){
let data7 = data.updated_at;
if(typeof data7 === "string"){
if(!pattern5.test(data7)){
const err15 = {instancePath:instancePath+"/updated_at",schemaPath:"#/$defs/utc/pattern",keyword:"pattern",params:{pattern: "^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"},message:"must match pattern \""+"^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"+"\""};
if(vErrors === null){
vErrors = [err15];
}
else {
vErrors.push(err15);
}
errors++;
}
if(!(formats0.validate(data7))){
const err16 = {instancePath:instancePath+"/updated_at",schemaPath:"#/$defs/utc/format",keyword:"format",params:{format: "date-time"},message:"must match format \""+"date-time"+"\""};
if(vErrors === null){
vErrors = [err16];
}
else {
vErrors.push(err16);
}
errors++;
}
}
else {
const err17 = {instancePath:instancePath+"/updated_at",schemaPath:"#/$defs/utc/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err17];
}
else {
vErrors.push(err17);
}
errors++;
}
}
}
else {
const err18 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err18];
}
else {
vErrors.push(err18);
}
errors++;
}
validate58.errors = vErrors;
return errors === 0;
}
validate58.evaluated = {"props":true,"dynamicProps":false,"dynamicItems":false};


function validate92(data, {instancePath="", parentData, parentDataProperty, rootData=data, dynamicAnchors={}}={}){
let vErrors = null;
let errors = 0;
const evaluated0 = validate92.evaluated;
if(evaluated0.dynamicProps){
evaluated0.props = undefined;
}
if(evaluated0.dynamicItems){
evaluated0.items = undefined;
}
if(data && typeof data == "object" && !Array.isArray(data)){
if((data.route_id === undefined) || (!(func0.call(data, "route_id")))){
const err0 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "route_id"},message:"must have required property '"+"route_id"+"'"};
if(vErrors === null){
vErrors = [err0];
}
else {
vErrors.push(err0);
}
errors++;
}
if((data.source === undefined) || (!(func0.call(data, "source")))){
const err1 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "source"},message:"must have required property '"+"source"+"'"};
if(vErrors === null){
vErrors = [err1];
}
else {
vErrors.push(err1);
}
errors++;
}
if((data.d0 === undefined) || (!(func0.call(data, "d0")))){
const err2 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "d0"},message:"must have required property '"+"d0"+"'"};
if(vErrors === null){
vErrors = [err2];
}
else {
vErrors.push(err2);
}
errors++;
}
if((data.locks === undefined) || (!(func0.call(data, "locks")))){
const err3 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "locks"},message:"must have required property '"+"locks"+"'"};
if(vErrors === null){
vErrors = [err3];
}
else {
vErrors.push(err3);
}
errors++;
}
for(const key0 of Object.keys(data)){
if(!((((key0 === "route_id") || (key0 === "source")) || (key0 === "d0")) || (key0 === "locks"))){
const err4 = {instancePath,schemaPath:"#/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key0},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err4];
}
else {
vErrors.push(err4);
}
errors++;
}
}
if(data.route_id !== undefined && func0.call(data, "route_id")){
if("D0" !== data.route_id){
const err5 = {instancePath:instancePath+"/route_id",schemaPath:"#/properties/route_id/const",keyword:"const",params:{allowedValue: "D0"},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err5];
}
else {
vErrors.push(err5);
}
errors++;
}
}
if(data.source !== undefined && func0.call(data, "source")){
if(!(validate22(data.source, {instancePath:instancePath+"/source",parentData:data,parentDataProperty:"source",rootData,dynamicAnchors}))){
vErrors = vErrors === null ? validate22.errors : vErrors.concat(validate22.errors);
errors = vErrors.length;
}
}
if(data.d0 !== undefined && func0.call(data, "d0")){
if(!(validate58(data.d0, {instancePath:instancePath+"/d0",parentData:data,parentDataProperty:"d0",rootData,dynamicAnchors}))){
vErrors = vErrors === null ? validate58.errors : vErrors.concat(validate58.errors);
errors = vErrors.length;
}
}
if(data.locks !== undefined && func0.call(data, "locks")){
let data3 = data.locks;
if(data3 && typeof data3 == "object" && !Array.isArray(data3)){
if((data3.promotion_allowed === undefined) || (!(func0.call(data3, "promotion_allowed")))){
const err6 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "promotion_allowed"},message:"must have required property '"+"promotion_allowed"+"'"};
if(vErrors === null){
vErrors = [err6];
}
else {
vErrors.push(err6);
}
errors++;
}
if((data3.model_build_allowed === undefined) || (!(func0.call(data3, "model_build_allowed")))){
const err7 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "model_build_allowed"},message:"must have required property '"+"model_build_allowed"+"'"};
if(vErrors === null){
vErrors = [err7];
}
else {
vErrors.push(err7);
}
errors++;
}
if((data3.paper_forward_allowed === undefined) || (!(func0.call(data3, "paper_forward_allowed")))){
const err8 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "paper_forward_allowed"},message:"must have required property '"+"paper_forward_allowed"+"'"};
if(vErrors === null){
vErrors = [err8];
}
else {
vErrors.push(err8);
}
errors++;
}
if((data3.live_broker_order_allowed === undefined) || (!(func0.call(data3, "live_broker_order_allowed")))){
const err9 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "live_broker_order_allowed"},message:"must have required property '"+"live_broker_order_allowed"+"'"};
if(vErrors === null){
vErrors = [err9];
}
else {
vErrors.push(err9);
}
errors++;
}
if((data3.profitability_claim_allowed === undefined) || (!(func0.call(data3, "profitability_claim_allowed")))){
const err10 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "profitability_claim_allowed"},message:"must have required property '"+"profitability_claim_allowed"+"'"};
if(vErrors === null){
vErrors = [err10];
}
else {
vErrors.push(err10);
}
errors++;
}
if((data3.go_summary_allowed === undefined) || (!(func0.call(data3, "go_summary_allowed")))){
const err11 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "go_summary_allowed"},message:"must have required property '"+"go_summary_allowed"+"'"};
if(vErrors === null){
vErrors = [err11];
}
else {
vErrors.push(err11);
}
errors++;
}
for(const key1 of Object.keys(data3)){
if(!((((((key1 === "promotion_allowed") || (key1 === "model_build_allowed")) || (key1 === "paper_forward_allowed")) || (key1 === "live_broker_order_allowed")) || (key1 === "profitability_claim_allowed")) || (key1 === "go_summary_allowed"))){
const err12 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key1},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err12];
}
else {
vErrors.push(err12);
}
errors++;
}
}
if(data3.promotion_allowed !== undefined && func0.call(data3, "promotion_allowed")){
if(false !== data3.promotion_allowed){
const err13 = {instancePath:instancePath+"/locks/promotion_allowed",schemaPath:"#/$defs/locks/properties/promotion_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err13];
}
else {
vErrors.push(err13);
}
errors++;
}
}
if(data3.model_build_allowed !== undefined && func0.call(data3, "model_build_allowed")){
if(false !== data3.model_build_allowed){
const err14 = {instancePath:instancePath+"/locks/model_build_allowed",schemaPath:"#/$defs/locks/properties/model_build_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err14];
}
else {
vErrors.push(err14);
}
errors++;
}
}
if(data3.paper_forward_allowed !== undefined && func0.call(data3, "paper_forward_allowed")){
if(false !== data3.paper_forward_allowed){
const err15 = {instancePath:instancePath+"/locks/paper_forward_allowed",schemaPath:"#/$defs/locks/properties/paper_forward_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err15];
}
else {
vErrors.push(err15);
}
errors++;
}
}
if(data3.live_broker_order_allowed !== undefined && func0.call(data3, "live_broker_order_allowed")){
if(false !== data3.live_broker_order_allowed){
const err16 = {instancePath:instancePath+"/locks/live_broker_order_allowed",schemaPath:"#/$defs/locks/properties/live_broker_order_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err16];
}
else {
vErrors.push(err16);
}
errors++;
}
}
if(data3.profitability_claim_allowed !== undefined && func0.call(data3, "profitability_claim_allowed")){
if(false !== data3.profitability_claim_allowed){
const err17 = {instancePath:instancePath+"/locks/profitability_claim_allowed",schemaPath:"#/$defs/locks/properties/profitability_claim_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err17];
}
else {
vErrors.push(err17);
}
errors++;
}
}
if(data3.go_summary_allowed !== undefined && func0.call(data3, "go_summary_allowed")){
if(false !== data3.go_summary_allowed){
const err18 = {instancePath:instancePath+"/locks/go_summary_allowed",schemaPath:"#/$defs/locks/properties/go_summary_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err18];
}
else {
vErrors.push(err18);
}
errors++;
}
}
}
else {
const err19 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err19];
}
else {
vErrors.push(err19);
}
errors++;
}
}
}
else {
const err20 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err20];
}
else {
vErrors.push(err20);
}
errors++;
}
validate92.errors = vErrors;
return errors === 0;
}
validate92.evaluated = {"props":true,"dynamicProps":false,"dynamicItems":false};

export const validateD1Root = validate95;
const schema93 = {"type":"object","additionalProperties":false,"required":["route_id","source","d1","locks"],"properties":{"route_id":{"const":"D1"},"source":{"$ref":"#/$defs/source"},"d1":{"$ref":"#/$defs/d1"},"locks":{"$ref":"#/$defs/locks"}}};
const schema94 = {"type":"object","additionalProperties":false,"required":["status","universe","source_sha256","updated_at"],"properties":{"status":{"enum":["PASS","FAIL","BLOCKED","PENDING"]},"universe":{"enum":["OFFICIAL","MANUAL_REVIEWED","UNKNOWN"]},"source_sha256":{"$ref":"#/$defs/sha256"},"updated_at":{"$ref":"#/$defs/utc"}},"allOf":[{"if":{"properties":{"status":{"const":"PASS"}}},"then":{"properties":{"universe":{"enum":["OFFICIAL","MANUAL_REVIEWED"]}}}},{"if":{"properties":{"universe":{"const":"UNKNOWN"}}},"then":{"properties":{"status":{"enum":["BLOCKED","PENDING"]}}}}]};

function validate63(data, {instancePath="", parentData, parentDataProperty, rootData=data, dynamicAnchors={}}={}){
let vErrors = null;
let errors = 0;
const evaluated0 = validate63.evaluated;
if(evaluated0.dynamicProps){
evaluated0.props = undefined;
}
if(evaluated0.dynamicItems){
evaluated0.items = undefined;
}
const _errs2 = errors;
let valid1 = true;
const _errs3 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
if(data.status !== undefined && func0.call(data, "status")){
if("PASS" !== data.status){
const err0 = {};
if(vErrors === null){
vErrors = [err0];
}
else {
vErrors.push(err0);
}
errors++;
}
}
}
var _valid0 = _errs3 === errors;
errors = _errs2;
if(vErrors !== null){
if(_errs2){
vErrors.length = _errs2;
}
else {
vErrors = null;
}
}
if(_valid0){
const _errs5 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
if(data.universe !== undefined && func0.call(data, "universe")){
let data1 = data.universe;
if(!((data1 === "OFFICIAL") || (data1 === "MANUAL_REVIEWED"))){
const err1 = {instancePath:instancePath+"/universe",schemaPath:"#/allOf/0/then/properties/universe/enum",keyword:"enum",params:{allowedValues: schema94.allOf[0].then.properties.universe.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err1];
}
else {
vErrors.push(err1);
}
errors++;
}
}
}
var _valid0 = _errs5 === errors;
valid1 = _valid0;
if(valid1){
var props0 = {};
props0.universe = true;
props0.status = true;
}
}
if(!valid1){
const err2 = {instancePath,schemaPath:"#/allOf/0/if",keyword:"if",params:{failingKeyword: "then"},message:"must match \"then\" schema"};
if(vErrors === null){
vErrors = [err2];
}
else {
vErrors.push(err2);
}
errors++;
}
const _errs8 = errors;
let valid4 = true;
const _errs9 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
if(data.universe !== undefined && func0.call(data, "universe")){
if("UNKNOWN" !== data.universe){
const err3 = {};
if(vErrors === null){
vErrors = [err3];
}
else {
vErrors.push(err3);
}
errors++;
}
}
}
var _valid1 = _errs9 === errors;
errors = _errs8;
if(vErrors !== null){
if(_errs8){
vErrors.length = _errs8;
}
else {
vErrors = null;
}
}
if(_valid1){
const _errs11 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
if(data.status !== undefined && func0.call(data, "status")){
let data3 = data.status;
if(!((data3 === "BLOCKED") || (data3 === "PENDING"))){
const err4 = {instancePath:instancePath+"/status",schemaPath:"#/allOf/1/then/properties/status/enum",keyword:"enum",params:{allowedValues: schema94.allOf[1].then.properties.status.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err4];
}
else {
vErrors.push(err4);
}
errors++;
}
}
}
var _valid1 = _errs11 === errors;
valid4 = _valid1;
if(valid4){
var props1 = {};
props1.status = true;
props1.universe = true;
}
}
if(!valid4){
const err5 = {instancePath,schemaPath:"#/allOf/1/if",keyword:"if",params:{failingKeyword: "then"},message:"must match \"then\" schema"};
if(vErrors === null){
vErrors = [err5];
}
else {
vErrors.push(err5);
}
errors++;
}
if(props0 !== true && props1 !== undefined){
if(props1 === true){
props0 = true;
}
else {
props0 = props0 || {};
Object.assign(props0, props1);
}
}
if(data && typeof data == "object" && !Array.isArray(data)){
if((data.status === undefined) || (!(func0.call(data, "status")))){
const err6 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "status"},message:"must have required property '"+"status"+"'"};
if(vErrors === null){
vErrors = [err6];
}
else {
vErrors.push(err6);
}
errors++;
}
if((data.universe === undefined) || (!(func0.call(data, "universe")))){
const err7 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "universe"},message:"must have required property '"+"universe"+"'"};
if(vErrors === null){
vErrors = [err7];
}
else {
vErrors.push(err7);
}
errors++;
}
if((data.source_sha256 === undefined) || (!(func0.call(data, "source_sha256")))){
const err8 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "source_sha256"},message:"must have required property '"+"source_sha256"+"'"};
if(vErrors === null){
vErrors = [err8];
}
else {
vErrors.push(err8);
}
errors++;
}
if((data.updated_at === undefined) || (!(func0.call(data, "updated_at")))){
const err9 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "updated_at"},message:"must have required property '"+"updated_at"+"'"};
if(vErrors === null){
vErrors = [err9];
}
else {
vErrors.push(err9);
}
errors++;
}
for(const key0 of Object.keys(data)){
if(!((((key0 === "status") || (key0 === "universe")) || (key0 === "source_sha256")) || (key0 === "updated_at"))){
const err10 = {instancePath,schemaPath:"#/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key0},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err10];
}
else {
vErrors.push(err10);
}
errors++;
}
}
if(data.status !== undefined && func0.call(data, "status")){
let data4 = data.status;
if(!((((data4 === "PASS") || (data4 === "FAIL")) || (data4 === "BLOCKED")) || (data4 === "PENDING"))){
const err11 = {instancePath:instancePath+"/status",schemaPath:"#/properties/status/enum",keyword:"enum",params:{allowedValues: schema94.properties.status.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err11];
}
else {
vErrors.push(err11);
}
errors++;
}
}
if(data.universe !== undefined && func0.call(data, "universe")){
let data5 = data.universe;
if(!(((data5 === "OFFICIAL") || (data5 === "MANUAL_REVIEWED")) || (data5 === "UNKNOWN"))){
const err12 = {instancePath:instancePath+"/universe",schemaPath:"#/properties/universe/enum",keyword:"enum",params:{allowedValues: schema94.properties.universe.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err12];
}
else {
vErrors.push(err12);
}
errors++;
}
}
if(data.source_sha256 !== undefined && func0.call(data, "source_sha256")){
let data6 = data.source_sha256;
if(typeof data6 === "string"){
if(!pattern4.test(data6)){
const err13 = {instancePath:instancePath+"/source_sha256",schemaPath:"#/$defs/sha256/pattern",keyword:"pattern",params:{pattern: "^[0-9a-f]{64}$"},message:"must match pattern \""+"^[0-9a-f]{64}$"+"\""};
if(vErrors === null){
vErrors = [err13];
}
else {
vErrors.push(err13);
}
errors++;
}
}
else {
const err14 = {instancePath:instancePath+"/source_sha256",schemaPath:"#/$defs/sha256/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err14];
}
else {
vErrors.push(err14);
}
errors++;
}
}
if(data.updated_at !== undefined && func0.call(data, "updated_at")){
let data7 = data.updated_at;
if(typeof data7 === "string"){
if(!pattern5.test(data7)){
const err15 = {instancePath:instancePath+"/updated_at",schemaPath:"#/$defs/utc/pattern",keyword:"pattern",params:{pattern: "^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"},message:"must match pattern \""+"^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"+"\""};
if(vErrors === null){
vErrors = [err15];
}
else {
vErrors.push(err15);
}
errors++;
}
if(!(formats0.validate(data7))){
const err16 = {instancePath:instancePath+"/updated_at",schemaPath:"#/$defs/utc/format",keyword:"format",params:{format: "date-time"},message:"must match format \""+"date-time"+"\""};
if(vErrors === null){
vErrors = [err16];
}
else {
vErrors.push(err16);
}
errors++;
}
}
else {
const err17 = {instancePath:instancePath+"/updated_at",schemaPath:"#/$defs/utc/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err17];
}
else {
vErrors.push(err17);
}
errors++;
}
}
}
else {
const err18 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err18];
}
else {
vErrors.push(err18);
}
errors++;
}
validate63.errors = vErrors;
return errors === 0;
}
validate63.evaluated = {"props":true,"dynamicProps":false,"dynamicItems":false};


function validate95(data, {instancePath="", parentData, parentDataProperty, rootData=data, dynamicAnchors={}}={}){
let vErrors = null;
let errors = 0;
const evaluated0 = validate95.evaluated;
if(evaluated0.dynamicProps){
evaluated0.props = undefined;
}
if(evaluated0.dynamicItems){
evaluated0.items = undefined;
}
if(data && typeof data == "object" && !Array.isArray(data)){
if((data.route_id === undefined) || (!(func0.call(data, "route_id")))){
const err0 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "route_id"},message:"must have required property '"+"route_id"+"'"};
if(vErrors === null){
vErrors = [err0];
}
else {
vErrors.push(err0);
}
errors++;
}
if((data.source === undefined) || (!(func0.call(data, "source")))){
const err1 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "source"},message:"must have required property '"+"source"+"'"};
if(vErrors === null){
vErrors = [err1];
}
else {
vErrors.push(err1);
}
errors++;
}
if((data.d1 === undefined) || (!(func0.call(data, "d1")))){
const err2 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "d1"},message:"must have required property '"+"d1"+"'"};
if(vErrors === null){
vErrors = [err2];
}
else {
vErrors.push(err2);
}
errors++;
}
if((data.locks === undefined) || (!(func0.call(data, "locks")))){
const err3 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "locks"},message:"must have required property '"+"locks"+"'"};
if(vErrors === null){
vErrors = [err3];
}
else {
vErrors.push(err3);
}
errors++;
}
for(const key0 of Object.keys(data)){
if(!((((key0 === "route_id") || (key0 === "source")) || (key0 === "d1")) || (key0 === "locks"))){
const err4 = {instancePath,schemaPath:"#/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key0},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err4];
}
else {
vErrors.push(err4);
}
errors++;
}
}
if(data.route_id !== undefined && func0.call(data, "route_id")){
if("D1" !== data.route_id){
const err5 = {instancePath:instancePath+"/route_id",schemaPath:"#/properties/route_id/const",keyword:"const",params:{allowedValue: "D1"},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err5];
}
else {
vErrors.push(err5);
}
errors++;
}
}
if(data.source !== undefined && func0.call(data, "source")){
if(!(validate22(data.source, {instancePath:instancePath+"/source",parentData:data,parentDataProperty:"source",rootData,dynamicAnchors}))){
vErrors = vErrors === null ? validate22.errors : vErrors.concat(validate22.errors);
errors = vErrors.length;
}
}
if(data.d1 !== undefined && func0.call(data, "d1")){
if(!(validate63(data.d1, {instancePath:instancePath+"/d1",parentData:data,parentDataProperty:"d1",rootData,dynamicAnchors}))){
vErrors = vErrors === null ? validate63.errors : vErrors.concat(validate63.errors);
errors = vErrors.length;
}
}
if(data.locks !== undefined && func0.call(data, "locks")){
let data3 = data.locks;
if(data3 && typeof data3 == "object" && !Array.isArray(data3)){
if((data3.promotion_allowed === undefined) || (!(func0.call(data3, "promotion_allowed")))){
const err6 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "promotion_allowed"},message:"must have required property '"+"promotion_allowed"+"'"};
if(vErrors === null){
vErrors = [err6];
}
else {
vErrors.push(err6);
}
errors++;
}
if((data3.model_build_allowed === undefined) || (!(func0.call(data3, "model_build_allowed")))){
const err7 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "model_build_allowed"},message:"must have required property '"+"model_build_allowed"+"'"};
if(vErrors === null){
vErrors = [err7];
}
else {
vErrors.push(err7);
}
errors++;
}
if((data3.paper_forward_allowed === undefined) || (!(func0.call(data3, "paper_forward_allowed")))){
const err8 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "paper_forward_allowed"},message:"must have required property '"+"paper_forward_allowed"+"'"};
if(vErrors === null){
vErrors = [err8];
}
else {
vErrors.push(err8);
}
errors++;
}
if((data3.live_broker_order_allowed === undefined) || (!(func0.call(data3, "live_broker_order_allowed")))){
const err9 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "live_broker_order_allowed"},message:"must have required property '"+"live_broker_order_allowed"+"'"};
if(vErrors === null){
vErrors = [err9];
}
else {
vErrors.push(err9);
}
errors++;
}
if((data3.profitability_claim_allowed === undefined) || (!(func0.call(data3, "profitability_claim_allowed")))){
const err10 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "profitability_claim_allowed"},message:"must have required property '"+"profitability_claim_allowed"+"'"};
if(vErrors === null){
vErrors = [err10];
}
else {
vErrors.push(err10);
}
errors++;
}
if((data3.go_summary_allowed === undefined) || (!(func0.call(data3, "go_summary_allowed")))){
const err11 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "go_summary_allowed"},message:"must have required property '"+"go_summary_allowed"+"'"};
if(vErrors === null){
vErrors = [err11];
}
else {
vErrors.push(err11);
}
errors++;
}
for(const key1 of Object.keys(data3)){
if(!((((((key1 === "promotion_allowed") || (key1 === "model_build_allowed")) || (key1 === "paper_forward_allowed")) || (key1 === "live_broker_order_allowed")) || (key1 === "profitability_claim_allowed")) || (key1 === "go_summary_allowed"))){
const err12 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key1},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err12];
}
else {
vErrors.push(err12);
}
errors++;
}
}
if(data3.promotion_allowed !== undefined && func0.call(data3, "promotion_allowed")){
if(false !== data3.promotion_allowed){
const err13 = {instancePath:instancePath+"/locks/promotion_allowed",schemaPath:"#/$defs/locks/properties/promotion_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err13];
}
else {
vErrors.push(err13);
}
errors++;
}
}
if(data3.model_build_allowed !== undefined && func0.call(data3, "model_build_allowed")){
if(false !== data3.model_build_allowed){
const err14 = {instancePath:instancePath+"/locks/model_build_allowed",schemaPath:"#/$defs/locks/properties/model_build_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err14];
}
else {
vErrors.push(err14);
}
errors++;
}
}
if(data3.paper_forward_allowed !== undefined && func0.call(data3, "paper_forward_allowed")){
if(false !== data3.paper_forward_allowed){
const err15 = {instancePath:instancePath+"/locks/paper_forward_allowed",schemaPath:"#/$defs/locks/properties/paper_forward_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err15];
}
else {
vErrors.push(err15);
}
errors++;
}
}
if(data3.live_broker_order_allowed !== undefined && func0.call(data3, "live_broker_order_allowed")){
if(false !== data3.live_broker_order_allowed){
const err16 = {instancePath:instancePath+"/locks/live_broker_order_allowed",schemaPath:"#/$defs/locks/properties/live_broker_order_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err16];
}
else {
vErrors.push(err16);
}
errors++;
}
}
if(data3.profitability_claim_allowed !== undefined && func0.call(data3, "profitability_claim_allowed")){
if(false !== data3.profitability_claim_allowed){
const err17 = {instancePath:instancePath+"/locks/profitability_claim_allowed",schemaPath:"#/$defs/locks/properties/profitability_claim_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err17];
}
else {
vErrors.push(err17);
}
errors++;
}
}
if(data3.go_summary_allowed !== undefined && func0.call(data3, "go_summary_allowed")){
if(false !== data3.go_summary_allowed){
const err18 = {instancePath:instancePath+"/locks/go_summary_allowed",schemaPath:"#/$defs/locks/properties/go_summary_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err18];
}
else {
vErrors.push(err18);
}
errors++;
}
}
}
else {
const err19 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err19];
}
else {
vErrors.push(err19);
}
errors++;
}
}
}
else {
const err20 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err20];
}
else {
vErrors.push(err20);
}
errors++;
}
validate95.errors = vErrors;
return errors === 0;
}
validate95.evaluated = {"props":true,"dynamicProps":false,"dynamicItems":false};

export const validateFixtureRoot = validate98;
const schema98 = {"type":"object","additionalProperties":false,"required":["route_id","source","fixture","locks"],"properties":{"route_id":{"const":"FIXTURE"},"source":{"$ref":"#/$defs/source"},"fixture":{"$ref":"#/$defs/fixture"},"locks":{"$ref":"#/$defs/locks"}}};
const schema99 = {"type":"object","additionalProperties":false,"required":["fixture_id","run","source_sha256","created_at"],"properties":{"fixture_id":{"$ref":"#/$defs/artifactId"},"run":{"$ref":"#/$defs/run"},"source_sha256":{"$ref":"#/$defs/sha256"},"created_at":{"$ref":"#/$defs/utc"}}};

function validate68(data, {instancePath="", parentData, parentDataProperty, rootData=data, dynamicAnchors={}}={}){
let vErrors = null;
let errors = 0;
const evaluated0 = validate68.evaluated;
if(evaluated0.dynamicProps){
evaluated0.props = undefined;
}
if(evaluated0.dynamicItems){
evaluated0.items = undefined;
}
if(data && typeof data == "object" && !Array.isArray(data)){
if((data.fixture_id === undefined) || (!(func0.call(data, "fixture_id")))){
const err0 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "fixture_id"},message:"must have required property '"+"fixture_id"+"'"};
if(vErrors === null){
vErrors = [err0];
}
else {
vErrors.push(err0);
}
errors++;
}
if((data.run === undefined) || (!(func0.call(data, "run")))){
const err1 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "run"},message:"must have required property '"+"run"+"'"};
if(vErrors === null){
vErrors = [err1];
}
else {
vErrors.push(err1);
}
errors++;
}
if((data.source_sha256 === undefined) || (!(func0.call(data, "source_sha256")))){
const err2 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "source_sha256"},message:"must have required property '"+"source_sha256"+"'"};
if(vErrors === null){
vErrors = [err2];
}
else {
vErrors.push(err2);
}
errors++;
}
if((data.created_at === undefined) || (!(func0.call(data, "created_at")))){
const err3 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "created_at"},message:"must have required property '"+"created_at"+"'"};
if(vErrors === null){
vErrors = [err3];
}
else {
vErrors.push(err3);
}
errors++;
}
for(const key0 of Object.keys(data)){
if(!((((key0 === "fixture_id") || (key0 === "run")) || (key0 === "source_sha256")) || (key0 === "created_at"))){
const err4 = {instancePath,schemaPath:"#/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key0},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err4];
}
else {
vErrors.push(err4);
}
errors++;
}
}
if(data.fixture_id !== undefined && func0.call(data, "fixture_id")){
let data0 = data.fixture_id;
if(typeof data0 === "string"){
if(!pattern20.test(data0)){
const err5 = {instancePath:instancePath+"/fixture_id",schemaPath:"#/$defs/artifactId/pattern",keyword:"pattern",params:{pattern: "^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"},message:"must match pattern \""+"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"+"\""};
if(vErrors === null){
vErrors = [err5];
}
else {
vErrors.push(err5);
}
errors++;
}
}
else {
const err6 = {instancePath:instancePath+"/fixture_id",schemaPath:"#/$defs/artifactId/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err6];
}
else {
vErrors.push(err6);
}
errors++;
}
}
if(data.run !== undefined && func0.call(data, "run")){
if(!(validate24(data.run, {instancePath:instancePath+"/run",parentData:data,parentDataProperty:"run",rootData,dynamicAnchors}))){
vErrors = vErrors === null ? validate24.errors : vErrors.concat(validate24.errors);
errors = vErrors.length;
}
}
if(data.source_sha256 !== undefined && func0.call(data, "source_sha256")){
let data2 = data.source_sha256;
if(typeof data2 === "string"){
if(!pattern4.test(data2)){
const err7 = {instancePath:instancePath+"/source_sha256",schemaPath:"#/$defs/sha256/pattern",keyword:"pattern",params:{pattern: "^[0-9a-f]{64}$"},message:"must match pattern \""+"^[0-9a-f]{64}$"+"\""};
if(vErrors === null){
vErrors = [err7];
}
else {
vErrors.push(err7);
}
errors++;
}
}
else {
const err8 = {instancePath:instancePath+"/source_sha256",schemaPath:"#/$defs/sha256/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err8];
}
else {
vErrors.push(err8);
}
errors++;
}
}
if(data.created_at !== undefined && func0.call(data, "created_at")){
let data3 = data.created_at;
if(typeof data3 === "string"){
if(!pattern5.test(data3)){
const err9 = {instancePath:instancePath+"/created_at",schemaPath:"#/$defs/utc/pattern",keyword:"pattern",params:{pattern: "^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"},message:"must match pattern \""+"^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{1,6})?Z$"+"\""};
if(vErrors === null){
vErrors = [err9];
}
else {
vErrors.push(err9);
}
errors++;
}
if(!(formats0.validate(data3))){
const err10 = {instancePath:instancePath+"/created_at",schemaPath:"#/$defs/utc/format",keyword:"format",params:{format: "date-time"},message:"must match format \""+"date-time"+"\""};
if(vErrors === null){
vErrors = [err10];
}
else {
vErrors.push(err10);
}
errors++;
}
}
else {
const err11 = {instancePath:instancePath+"/created_at",schemaPath:"#/$defs/utc/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err11];
}
else {
vErrors.push(err11);
}
errors++;
}
}
}
else {
const err12 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err12];
}
else {
vErrors.push(err12);
}
errors++;
}
validate68.errors = vErrors;
return errors === 0;
}
validate68.evaluated = {"props":true,"dynamicProps":false,"dynamicItems":false};


function validate98(data, {instancePath="", parentData, parentDataProperty, rootData=data, dynamicAnchors={}}={}){
let vErrors = null;
let errors = 0;
const evaluated0 = validate98.evaluated;
if(evaluated0.dynamicProps){
evaluated0.props = undefined;
}
if(evaluated0.dynamicItems){
evaluated0.items = undefined;
}
if(data && typeof data == "object" && !Array.isArray(data)){
if((data.route_id === undefined) || (!(func0.call(data, "route_id")))){
const err0 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "route_id"},message:"must have required property '"+"route_id"+"'"};
if(vErrors === null){
vErrors = [err0];
}
else {
vErrors.push(err0);
}
errors++;
}
if((data.source === undefined) || (!(func0.call(data, "source")))){
const err1 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "source"},message:"must have required property '"+"source"+"'"};
if(vErrors === null){
vErrors = [err1];
}
else {
vErrors.push(err1);
}
errors++;
}
if((data.fixture === undefined) || (!(func0.call(data, "fixture")))){
const err2 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "fixture"},message:"must have required property '"+"fixture"+"'"};
if(vErrors === null){
vErrors = [err2];
}
else {
vErrors.push(err2);
}
errors++;
}
if((data.locks === undefined) || (!(func0.call(data, "locks")))){
const err3 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "locks"},message:"must have required property '"+"locks"+"'"};
if(vErrors === null){
vErrors = [err3];
}
else {
vErrors.push(err3);
}
errors++;
}
for(const key0 of Object.keys(data)){
if(!((((key0 === "route_id") || (key0 === "source")) || (key0 === "fixture")) || (key0 === "locks"))){
const err4 = {instancePath,schemaPath:"#/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key0},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err4];
}
else {
vErrors.push(err4);
}
errors++;
}
}
if(data.route_id !== undefined && func0.call(data, "route_id")){
if("FIXTURE" !== data.route_id){
const err5 = {instancePath:instancePath+"/route_id",schemaPath:"#/properties/route_id/const",keyword:"const",params:{allowedValue: "FIXTURE"},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err5];
}
else {
vErrors.push(err5);
}
errors++;
}
}
if(data.source !== undefined && func0.call(data, "source")){
if(!(validate22(data.source, {instancePath:instancePath+"/source",parentData:data,parentDataProperty:"source",rootData,dynamicAnchors}))){
vErrors = vErrors === null ? validate22.errors : vErrors.concat(validate22.errors);
errors = vErrors.length;
}
}
if(data.fixture !== undefined && func0.call(data, "fixture")){
if(!(validate68(data.fixture, {instancePath:instancePath+"/fixture",parentData:data,parentDataProperty:"fixture",rootData,dynamicAnchors}))){
vErrors = vErrors === null ? validate68.errors : vErrors.concat(validate68.errors);
errors = vErrors.length;
}
}
if(data.locks !== undefined && func0.call(data, "locks")){
let data3 = data.locks;
if(data3 && typeof data3 == "object" && !Array.isArray(data3)){
if((data3.promotion_allowed === undefined) || (!(func0.call(data3, "promotion_allowed")))){
const err6 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "promotion_allowed"},message:"must have required property '"+"promotion_allowed"+"'"};
if(vErrors === null){
vErrors = [err6];
}
else {
vErrors.push(err6);
}
errors++;
}
if((data3.model_build_allowed === undefined) || (!(func0.call(data3, "model_build_allowed")))){
const err7 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "model_build_allowed"},message:"must have required property '"+"model_build_allowed"+"'"};
if(vErrors === null){
vErrors = [err7];
}
else {
vErrors.push(err7);
}
errors++;
}
if((data3.paper_forward_allowed === undefined) || (!(func0.call(data3, "paper_forward_allowed")))){
const err8 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "paper_forward_allowed"},message:"must have required property '"+"paper_forward_allowed"+"'"};
if(vErrors === null){
vErrors = [err8];
}
else {
vErrors.push(err8);
}
errors++;
}
if((data3.live_broker_order_allowed === undefined) || (!(func0.call(data3, "live_broker_order_allowed")))){
const err9 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "live_broker_order_allowed"},message:"must have required property '"+"live_broker_order_allowed"+"'"};
if(vErrors === null){
vErrors = [err9];
}
else {
vErrors.push(err9);
}
errors++;
}
if((data3.profitability_claim_allowed === undefined) || (!(func0.call(data3, "profitability_claim_allowed")))){
const err10 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "profitability_claim_allowed"},message:"must have required property '"+"profitability_claim_allowed"+"'"};
if(vErrors === null){
vErrors = [err10];
}
else {
vErrors.push(err10);
}
errors++;
}
if((data3.go_summary_allowed === undefined) || (!(func0.call(data3, "go_summary_allowed")))){
const err11 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/required",keyword:"required",params:{missingProperty: "go_summary_allowed"},message:"must have required property '"+"go_summary_allowed"+"'"};
if(vErrors === null){
vErrors = [err11];
}
else {
vErrors.push(err11);
}
errors++;
}
for(const key1 of Object.keys(data3)){
if(!((((((key1 === "promotion_allowed") || (key1 === "model_build_allowed")) || (key1 === "paper_forward_allowed")) || (key1 === "live_broker_order_allowed")) || (key1 === "profitability_claim_allowed")) || (key1 === "go_summary_allowed"))){
const err12 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key1},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err12];
}
else {
vErrors.push(err12);
}
errors++;
}
}
if(data3.promotion_allowed !== undefined && func0.call(data3, "promotion_allowed")){
if(false !== data3.promotion_allowed){
const err13 = {instancePath:instancePath+"/locks/promotion_allowed",schemaPath:"#/$defs/locks/properties/promotion_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err13];
}
else {
vErrors.push(err13);
}
errors++;
}
}
if(data3.model_build_allowed !== undefined && func0.call(data3, "model_build_allowed")){
if(false !== data3.model_build_allowed){
const err14 = {instancePath:instancePath+"/locks/model_build_allowed",schemaPath:"#/$defs/locks/properties/model_build_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err14];
}
else {
vErrors.push(err14);
}
errors++;
}
}
if(data3.paper_forward_allowed !== undefined && func0.call(data3, "paper_forward_allowed")){
if(false !== data3.paper_forward_allowed){
const err15 = {instancePath:instancePath+"/locks/paper_forward_allowed",schemaPath:"#/$defs/locks/properties/paper_forward_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err15];
}
else {
vErrors.push(err15);
}
errors++;
}
}
if(data3.live_broker_order_allowed !== undefined && func0.call(data3, "live_broker_order_allowed")){
if(false !== data3.live_broker_order_allowed){
const err16 = {instancePath:instancePath+"/locks/live_broker_order_allowed",schemaPath:"#/$defs/locks/properties/live_broker_order_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err16];
}
else {
vErrors.push(err16);
}
errors++;
}
}
if(data3.profitability_claim_allowed !== undefined && func0.call(data3, "profitability_claim_allowed")){
if(false !== data3.profitability_claim_allowed){
const err17 = {instancePath:instancePath+"/locks/profitability_claim_allowed",schemaPath:"#/$defs/locks/properties/profitability_claim_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err17];
}
else {
vErrors.push(err17);
}
errors++;
}
}
if(data3.go_summary_allowed !== undefined && func0.call(data3, "go_summary_allowed")){
if(false !== data3.go_summary_allowed){
const err18 = {instancePath:instancePath+"/locks/go_summary_allowed",schemaPath:"#/$defs/locks/properties/go_summary_allowed/const",keyword:"const",params:{allowedValue: false},message:"must be equal to constant"};
if(vErrors === null){
vErrors = [err18];
}
else {
vErrors.push(err18);
}
errors++;
}
}
}
else {
const err19 = {instancePath:instancePath+"/locks",schemaPath:"#/$defs/locks/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err19];
}
else {
vErrors.push(err19);
}
errors++;
}
}
}
else {
const err20 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err20];
}
else {
vErrors.push(err20);
}
errors++;
}
validate98.errors = vErrors;
return errors === 0;
}
validate98.evaluated = {"props":true,"dynamicProps":false,"dynamicItems":false};

export const validateErrorRoot = validate101;
const schema104 = {"type":"object","additionalProperties":false,"required":["route_id","error"],"properties":{"route_id":{"$ref":"#/$defs/routeId"},"error":{"$ref":"#/$defs/error"}},"allOf":[{"if":{"properties":{"route_id":{"const":"RUNS"}},"required":["route_id"]},"then":{"properties":{"error":{"type":"object","required":["code"],"properties":{"code":{"enum":["BAD_REQUEST","INVALID_CURSOR","INTERNAL_ERROR"]}}}}}},{"if":{"properties":{"route_id":{"const":"RUN_DETAIL"}},"required":["route_id"]},"then":{"properties":{"error":{"type":"object","required":["code"],"properties":{"code":{"enum":["NOT_FOUND","INTERNAL_ERROR"]}}}}}},{"if":{"properties":{"route_id":{"const":"EVENTS"}},"required":["route_id"]},"then":{"properties":{"error":{"type":"object","required":["code"],"properties":{"code":{"enum":["NOT_FOUND","INVALID_CURSOR","INTERNAL_ERROR"]}}}}}},{"if":{"properties":{"route_id":{"const":"MATRIX"}},"required":["route_id"]},"then":{"properties":{"error":{"type":"object","required":["code"],"properties":{"code":{"enum":["INTERNAL_ERROR"]}}}}}},{"if":{"properties":{"route_id":{"const":"LEDGER"}},"required":["route_id"]},"then":{"properties":{"error":{"type":"object","required":["code"],"properties":{"code":{"enum":["INVALID_CURSOR","INTERNAL_ERROR"]}}}}}},{"if":{"properties":{"route_id":{"const":"ARTIFACTS"}},"required":["route_id"]},"then":{"properties":{"error":{"type":"object","required":["code"],"properties":{"code":{"enum":["INVALID_CURSOR","INTERNAL_ERROR"]}}}}}},{"if":{"properties":{"route_id":{"const":"D0"}},"required":["route_id"]},"then":{"properties":{"error":{"type":"object","required":["code"],"properties":{"code":{"enum":["INTERNAL_ERROR"]}}}}}},{"if":{"properties":{"route_id":{"const":"D1"}},"required":["route_id"]},"then":{"properties":{"error":{"type":"object","required":["code"],"properties":{"code":{"enum":["INTERNAL_ERROR"]}}}}}},{"if":{"properties":{"route_id":{"const":"FIXTURE"}},"required":["route_id"]},"then":{"properties":{"error":{"type":"object","required":["code"],"properties":{"code":{"enum":["INTERNAL_ERROR"]}}}}}}]};
const schema105 = {"enum":["RUNS","RUN_DETAIL","EVENTS","MATRIX","LEDGER","ARTIFACTS","D0","D1","FIXTURE"]};
const schema106 = {"type":"object","additionalProperties":false,"required":["code","message"],"properties":{"code":{"enum":["BAD_REQUEST","NOT_FOUND","INVALID_CURSOR","VALIDATION_ERROR","INTERNAL_ERROR"]},"message":{"type":"string","minLength":1}}};

function validate101(data, {instancePath="", parentData, parentDataProperty, rootData=data, dynamicAnchors={}}={}){
let vErrors = null;
let errors = 0;
const evaluated0 = validate101.evaluated;
if(evaluated0.dynamicProps){
evaluated0.props = undefined;
}
if(evaluated0.dynamicItems){
evaluated0.items = undefined;
}
const _errs2 = errors;
let valid1 = true;
const _errs3 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
let missing0;
if(((data.route_id === undefined) || (!(func0.call(data, "route_id")))) && (missing0 = "route_id")){
const err0 = {};
if(vErrors === null){
vErrors = [err0];
}
else {
vErrors.push(err0);
}
errors++;
}
else {
if(data.route_id !== undefined && func0.call(data, "route_id")){
if("RUNS" !== data.route_id){
const err1 = {};
if(vErrors === null){
vErrors = [err1];
}
else {
vErrors.push(err1);
}
errors++;
}
}
}
}
var _valid0 = _errs3 === errors;
errors = _errs2;
if(vErrors !== null){
if(_errs2){
vErrors.length = _errs2;
}
else {
vErrors = null;
}
}
if(_valid0){
const _errs5 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
if(data.error !== undefined && func0.call(data, "error")){
let data1 = data.error;
if(data1 && typeof data1 == "object" && !Array.isArray(data1)){
if((data1.code === undefined) || (!(func0.call(data1, "code")))){
const err2 = {instancePath:instancePath+"/error",schemaPath:"#/allOf/0/then/properties/error/required",keyword:"required",params:{missingProperty: "code"},message:"must have required property '"+"code"+"'"};
if(vErrors === null){
vErrors = [err2];
}
else {
vErrors.push(err2);
}
errors++;
}
if(data1.code !== undefined && func0.call(data1, "code")){
let data2 = data1.code;
if(!(((data2 === "BAD_REQUEST") || (data2 === "INVALID_CURSOR")) || (data2 === "INTERNAL_ERROR"))){
const err3 = {instancePath:instancePath+"/error/code",schemaPath:"#/allOf/0/then/properties/error/properties/code/enum",keyword:"enum",params:{allowedValues: schema104.allOf[0].then.properties.error.properties.code.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err3];
}
else {
vErrors.push(err3);
}
errors++;
}
}
}
else {
const err4 = {instancePath:instancePath+"/error",schemaPath:"#/allOf/0/then/properties/error/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err4];
}
else {
vErrors.push(err4);
}
errors++;
}
}
}
var _valid0 = _errs5 === errors;
valid1 = _valid0;
if(valid1){
var props0 = {};
props0.error = true;
props0.route_id = true;
}
}
if(!valid1){
const err5 = {instancePath,schemaPath:"#/allOf/0/if",keyword:"if",params:{failingKeyword: "then"},message:"must match \"then\" schema"};
if(vErrors === null){
vErrors = [err5];
}
else {
vErrors.push(err5);
}
errors++;
}
const _errs10 = errors;
let valid5 = true;
const _errs11 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
let missing1;
if(((data.route_id === undefined) || (!(func0.call(data, "route_id")))) && (missing1 = "route_id")){
const err6 = {};
if(vErrors === null){
vErrors = [err6];
}
else {
vErrors.push(err6);
}
errors++;
}
else {
if(data.route_id !== undefined && func0.call(data, "route_id")){
if("RUN_DETAIL" !== data.route_id){
const err7 = {};
if(vErrors === null){
vErrors = [err7];
}
else {
vErrors.push(err7);
}
errors++;
}
}
}
}
var _valid1 = _errs11 === errors;
errors = _errs10;
if(vErrors !== null){
if(_errs10){
vErrors.length = _errs10;
}
else {
vErrors = null;
}
}
if(_valid1){
const _errs13 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
if(data.error !== undefined && func0.call(data, "error")){
let data4 = data.error;
if(data4 && typeof data4 == "object" && !Array.isArray(data4)){
if((data4.code === undefined) || (!(func0.call(data4, "code")))){
const err8 = {instancePath:instancePath+"/error",schemaPath:"#/allOf/1/then/properties/error/required",keyword:"required",params:{missingProperty: "code"},message:"must have required property '"+"code"+"'"};
if(vErrors === null){
vErrors = [err8];
}
else {
vErrors.push(err8);
}
errors++;
}
if(data4.code !== undefined && func0.call(data4, "code")){
let data5 = data4.code;
if(!((data5 === "NOT_FOUND") || (data5 === "INTERNAL_ERROR"))){
const err9 = {instancePath:instancePath+"/error/code",schemaPath:"#/allOf/1/then/properties/error/properties/code/enum",keyword:"enum",params:{allowedValues: schema104.allOf[1].then.properties.error.properties.code.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err9];
}
else {
vErrors.push(err9);
}
errors++;
}
}
}
else {
const err10 = {instancePath:instancePath+"/error",schemaPath:"#/allOf/1/then/properties/error/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err10];
}
else {
vErrors.push(err10);
}
errors++;
}
}
}
var _valid1 = _errs13 === errors;
valid5 = _valid1;
if(valid5){
var props1 = {};
props1.error = true;
props1.route_id = true;
}
}
if(!valid5){
const err11 = {instancePath,schemaPath:"#/allOf/1/if",keyword:"if",params:{failingKeyword: "then"},message:"must match \"then\" schema"};
if(vErrors === null){
vErrors = [err11];
}
else {
vErrors.push(err11);
}
errors++;
}
if(props0 !== true && props1 !== undefined){
if(props1 === true){
props0 = true;
}
else {
props0 = props0 || {};
Object.assign(props0, props1);
}
}
const _errs18 = errors;
let valid9 = true;
const _errs19 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
let missing2;
if(((data.route_id === undefined) || (!(func0.call(data, "route_id")))) && (missing2 = "route_id")){
const err12 = {};
if(vErrors === null){
vErrors = [err12];
}
else {
vErrors.push(err12);
}
errors++;
}
else {
if(data.route_id !== undefined && func0.call(data, "route_id")){
if("EVENTS" !== data.route_id){
const err13 = {};
if(vErrors === null){
vErrors = [err13];
}
else {
vErrors.push(err13);
}
errors++;
}
}
}
}
var _valid2 = _errs19 === errors;
errors = _errs18;
if(vErrors !== null){
if(_errs18){
vErrors.length = _errs18;
}
else {
vErrors = null;
}
}
if(_valid2){
const _errs21 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
if(data.error !== undefined && func0.call(data, "error")){
let data7 = data.error;
if(data7 && typeof data7 == "object" && !Array.isArray(data7)){
if((data7.code === undefined) || (!(func0.call(data7, "code")))){
const err14 = {instancePath:instancePath+"/error",schemaPath:"#/allOf/2/then/properties/error/required",keyword:"required",params:{missingProperty: "code"},message:"must have required property '"+"code"+"'"};
if(vErrors === null){
vErrors = [err14];
}
else {
vErrors.push(err14);
}
errors++;
}
if(data7.code !== undefined && func0.call(data7, "code")){
let data8 = data7.code;
if(!(((data8 === "NOT_FOUND") || (data8 === "INVALID_CURSOR")) || (data8 === "INTERNAL_ERROR"))){
const err15 = {instancePath:instancePath+"/error/code",schemaPath:"#/allOf/2/then/properties/error/properties/code/enum",keyword:"enum",params:{allowedValues: schema104.allOf[2].then.properties.error.properties.code.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err15];
}
else {
vErrors.push(err15);
}
errors++;
}
}
}
else {
const err16 = {instancePath:instancePath+"/error",schemaPath:"#/allOf/2/then/properties/error/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err16];
}
else {
vErrors.push(err16);
}
errors++;
}
}
}
var _valid2 = _errs21 === errors;
valid9 = _valid2;
if(valid9){
var props2 = {};
props2.error = true;
props2.route_id = true;
}
}
if(!valid9){
const err17 = {instancePath,schemaPath:"#/allOf/2/if",keyword:"if",params:{failingKeyword: "then"},message:"must match \"then\" schema"};
if(vErrors === null){
vErrors = [err17];
}
else {
vErrors.push(err17);
}
errors++;
}
if(props0 !== true && props2 !== undefined){
if(props2 === true){
props0 = true;
}
else {
props0 = props0 || {};
Object.assign(props0, props2);
}
}
const _errs26 = errors;
let valid13 = true;
const _errs27 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
let missing3;
if(((data.route_id === undefined) || (!(func0.call(data, "route_id")))) && (missing3 = "route_id")){
const err18 = {};
if(vErrors === null){
vErrors = [err18];
}
else {
vErrors.push(err18);
}
errors++;
}
else {
if(data.route_id !== undefined && func0.call(data, "route_id")){
if("MATRIX" !== data.route_id){
const err19 = {};
if(vErrors === null){
vErrors = [err19];
}
else {
vErrors.push(err19);
}
errors++;
}
}
}
}
var _valid3 = _errs27 === errors;
errors = _errs26;
if(vErrors !== null){
if(_errs26){
vErrors.length = _errs26;
}
else {
vErrors = null;
}
}
if(_valid3){
const _errs29 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
if(data.error !== undefined && func0.call(data, "error")){
let data10 = data.error;
if(data10 && typeof data10 == "object" && !Array.isArray(data10)){
if((data10.code === undefined) || (!(func0.call(data10, "code")))){
const err20 = {instancePath:instancePath+"/error",schemaPath:"#/allOf/3/then/properties/error/required",keyword:"required",params:{missingProperty: "code"},message:"must have required property '"+"code"+"'"};
if(vErrors === null){
vErrors = [err20];
}
else {
vErrors.push(err20);
}
errors++;
}
if(data10.code !== undefined && func0.call(data10, "code")){
if(!(data10.code === "INTERNAL_ERROR")){
const err21 = {instancePath:instancePath+"/error/code",schemaPath:"#/allOf/3/then/properties/error/properties/code/enum",keyword:"enum",params:{allowedValues: schema104.allOf[3].then.properties.error.properties.code.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err21];
}
else {
vErrors.push(err21);
}
errors++;
}
}
}
else {
const err22 = {instancePath:instancePath+"/error",schemaPath:"#/allOf/3/then/properties/error/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err22];
}
else {
vErrors.push(err22);
}
errors++;
}
}
}
var _valid3 = _errs29 === errors;
valid13 = _valid3;
if(valid13){
var props3 = {};
props3.error = true;
props3.route_id = true;
}
}
if(!valid13){
const err23 = {instancePath,schemaPath:"#/allOf/3/if",keyword:"if",params:{failingKeyword: "then"},message:"must match \"then\" schema"};
if(vErrors === null){
vErrors = [err23];
}
else {
vErrors.push(err23);
}
errors++;
}
if(props0 !== true && props3 !== undefined){
if(props3 === true){
props0 = true;
}
else {
props0 = props0 || {};
Object.assign(props0, props3);
}
}
const _errs34 = errors;
let valid17 = true;
const _errs35 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
let missing4;
if(((data.route_id === undefined) || (!(func0.call(data, "route_id")))) && (missing4 = "route_id")){
const err24 = {};
if(vErrors === null){
vErrors = [err24];
}
else {
vErrors.push(err24);
}
errors++;
}
else {
if(data.route_id !== undefined && func0.call(data, "route_id")){
if("LEDGER" !== data.route_id){
const err25 = {};
if(vErrors === null){
vErrors = [err25];
}
else {
vErrors.push(err25);
}
errors++;
}
}
}
}
var _valid4 = _errs35 === errors;
errors = _errs34;
if(vErrors !== null){
if(_errs34){
vErrors.length = _errs34;
}
else {
vErrors = null;
}
}
if(_valid4){
const _errs37 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
if(data.error !== undefined && func0.call(data, "error")){
let data13 = data.error;
if(data13 && typeof data13 == "object" && !Array.isArray(data13)){
if((data13.code === undefined) || (!(func0.call(data13, "code")))){
const err26 = {instancePath:instancePath+"/error",schemaPath:"#/allOf/4/then/properties/error/required",keyword:"required",params:{missingProperty: "code"},message:"must have required property '"+"code"+"'"};
if(vErrors === null){
vErrors = [err26];
}
else {
vErrors.push(err26);
}
errors++;
}
if(data13.code !== undefined && func0.call(data13, "code")){
let data14 = data13.code;
if(!((data14 === "INVALID_CURSOR") || (data14 === "INTERNAL_ERROR"))){
const err27 = {instancePath:instancePath+"/error/code",schemaPath:"#/allOf/4/then/properties/error/properties/code/enum",keyword:"enum",params:{allowedValues: schema104.allOf[4].then.properties.error.properties.code.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err27];
}
else {
vErrors.push(err27);
}
errors++;
}
}
}
else {
const err28 = {instancePath:instancePath+"/error",schemaPath:"#/allOf/4/then/properties/error/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err28];
}
else {
vErrors.push(err28);
}
errors++;
}
}
}
var _valid4 = _errs37 === errors;
valid17 = _valid4;
if(valid17){
var props4 = {};
props4.error = true;
props4.route_id = true;
}
}
if(!valid17){
const err29 = {instancePath,schemaPath:"#/allOf/4/if",keyword:"if",params:{failingKeyword: "then"},message:"must match \"then\" schema"};
if(vErrors === null){
vErrors = [err29];
}
else {
vErrors.push(err29);
}
errors++;
}
if(props0 !== true && props4 !== undefined){
if(props4 === true){
props0 = true;
}
else {
props0 = props0 || {};
Object.assign(props0, props4);
}
}
const _errs42 = errors;
let valid21 = true;
const _errs43 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
let missing5;
if(((data.route_id === undefined) || (!(func0.call(data, "route_id")))) && (missing5 = "route_id")){
const err30 = {};
if(vErrors === null){
vErrors = [err30];
}
else {
vErrors.push(err30);
}
errors++;
}
else {
if(data.route_id !== undefined && func0.call(data, "route_id")){
if("ARTIFACTS" !== data.route_id){
const err31 = {};
if(vErrors === null){
vErrors = [err31];
}
else {
vErrors.push(err31);
}
errors++;
}
}
}
}
var _valid5 = _errs43 === errors;
errors = _errs42;
if(vErrors !== null){
if(_errs42){
vErrors.length = _errs42;
}
else {
vErrors = null;
}
}
if(_valid5){
const _errs45 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
if(data.error !== undefined && func0.call(data, "error")){
let data16 = data.error;
if(data16 && typeof data16 == "object" && !Array.isArray(data16)){
if((data16.code === undefined) || (!(func0.call(data16, "code")))){
const err32 = {instancePath:instancePath+"/error",schemaPath:"#/allOf/5/then/properties/error/required",keyword:"required",params:{missingProperty: "code"},message:"must have required property '"+"code"+"'"};
if(vErrors === null){
vErrors = [err32];
}
else {
vErrors.push(err32);
}
errors++;
}
if(data16.code !== undefined && func0.call(data16, "code")){
let data17 = data16.code;
if(!((data17 === "INVALID_CURSOR") || (data17 === "INTERNAL_ERROR"))){
const err33 = {instancePath:instancePath+"/error/code",schemaPath:"#/allOf/5/then/properties/error/properties/code/enum",keyword:"enum",params:{allowedValues: schema104.allOf[5].then.properties.error.properties.code.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err33];
}
else {
vErrors.push(err33);
}
errors++;
}
}
}
else {
const err34 = {instancePath:instancePath+"/error",schemaPath:"#/allOf/5/then/properties/error/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err34];
}
else {
vErrors.push(err34);
}
errors++;
}
}
}
var _valid5 = _errs45 === errors;
valid21 = _valid5;
if(valid21){
var props5 = {};
props5.error = true;
props5.route_id = true;
}
}
if(!valid21){
const err35 = {instancePath,schemaPath:"#/allOf/5/if",keyword:"if",params:{failingKeyword: "then"},message:"must match \"then\" schema"};
if(vErrors === null){
vErrors = [err35];
}
else {
vErrors.push(err35);
}
errors++;
}
if(props0 !== true && props5 !== undefined){
if(props5 === true){
props0 = true;
}
else {
props0 = props0 || {};
Object.assign(props0, props5);
}
}
const _errs50 = errors;
let valid25 = true;
const _errs51 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
let missing6;
if(((data.route_id === undefined) || (!(func0.call(data, "route_id")))) && (missing6 = "route_id")){
const err36 = {};
if(vErrors === null){
vErrors = [err36];
}
else {
vErrors.push(err36);
}
errors++;
}
else {
if(data.route_id !== undefined && func0.call(data, "route_id")){
if("D0" !== data.route_id){
const err37 = {};
if(vErrors === null){
vErrors = [err37];
}
else {
vErrors.push(err37);
}
errors++;
}
}
}
}
var _valid6 = _errs51 === errors;
errors = _errs50;
if(vErrors !== null){
if(_errs50){
vErrors.length = _errs50;
}
else {
vErrors = null;
}
}
if(_valid6){
const _errs53 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
if(data.error !== undefined && func0.call(data, "error")){
let data19 = data.error;
if(data19 && typeof data19 == "object" && !Array.isArray(data19)){
if((data19.code === undefined) || (!(func0.call(data19, "code")))){
const err38 = {instancePath:instancePath+"/error",schemaPath:"#/allOf/6/then/properties/error/required",keyword:"required",params:{missingProperty: "code"},message:"must have required property '"+"code"+"'"};
if(vErrors === null){
vErrors = [err38];
}
else {
vErrors.push(err38);
}
errors++;
}
if(data19.code !== undefined && func0.call(data19, "code")){
if(!(data19.code === "INTERNAL_ERROR")){
const err39 = {instancePath:instancePath+"/error/code",schemaPath:"#/allOf/6/then/properties/error/properties/code/enum",keyword:"enum",params:{allowedValues: schema104.allOf[6].then.properties.error.properties.code.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err39];
}
else {
vErrors.push(err39);
}
errors++;
}
}
}
else {
const err40 = {instancePath:instancePath+"/error",schemaPath:"#/allOf/6/then/properties/error/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err40];
}
else {
vErrors.push(err40);
}
errors++;
}
}
}
var _valid6 = _errs53 === errors;
valid25 = _valid6;
if(valid25){
var props6 = {};
props6.error = true;
props6.route_id = true;
}
}
if(!valid25){
const err41 = {instancePath,schemaPath:"#/allOf/6/if",keyword:"if",params:{failingKeyword: "then"},message:"must match \"then\" schema"};
if(vErrors === null){
vErrors = [err41];
}
else {
vErrors.push(err41);
}
errors++;
}
if(props0 !== true && props6 !== undefined){
if(props6 === true){
props0 = true;
}
else {
props0 = props0 || {};
Object.assign(props0, props6);
}
}
const _errs58 = errors;
let valid29 = true;
const _errs59 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
let missing7;
if(((data.route_id === undefined) || (!(func0.call(data, "route_id")))) && (missing7 = "route_id")){
const err42 = {};
if(vErrors === null){
vErrors = [err42];
}
else {
vErrors.push(err42);
}
errors++;
}
else {
if(data.route_id !== undefined && func0.call(data, "route_id")){
if("D1" !== data.route_id){
const err43 = {};
if(vErrors === null){
vErrors = [err43];
}
else {
vErrors.push(err43);
}
errors++;
}
}
}
}
var _valid7 = _errs59 === errors;
errors = _errs58;
if(vErrors !== null){
if(_errs58){
vErrors.length = _errs58;
}
else {
vErrors = null;
}
}
if(_valid7){
const _errs61 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
if(data.error !== undefined && func0.call(data, "error")){
let data22 = data.error;
if(data22 && typeof data22 == "object" && !Array.isArray(data22)){
if((data22.code === undefined) || (!(func0.call(data22, "code")))){
const err44 = {instancePath:instancePath+"/error",schemaPath:"#/allOf/7/then/properties/error/required",keyword:"required",params:{missingProperty: "code"},message:"must have required property '"+"code"+"'"};
if(vErrors === null){
vErrors = [err44];
}
else {
vErrors.push(err44);
}
errors++;
}
if(data22.code !== undefined && func0.call(data22, "code")){
if(!(data22.code === "INTERNAL_ERROR")){
const err45 = {instancePath:instancePath+"/error/code",schemaPath:"#/allOf/7/then/properties/error/properties/code/enum",keyword:"enum",params:{allowedValues: schema104.allOf[7].then.properties.error.properties.code.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err45];
}
else {
vErrors.push(err45);
}
errors++;
}
}
}
else {
const err46 = {instancePath:instancePath+"/error",schemaPath:"#/allOf/7/then/properties/error/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err46];
}
else {
vErrors.push(err46);
}
errors++;
}
}
}
var _valid7 = _errs61 === errors;
valid29 = _valid7;
if(valid29){
var props7 = {};
props7.error = true;
props7.route_id = true;
}
}
if(!valid29){
const err47 = {instancePath,schemaPath:"#/allOf/7/if",keyword:"if",params:{failingKeyword: "then"},message:"must match \"then\" schema"};
if(vErrors === null){
vErrors = [err47];
}
else {
vErrors.push(err47);
}
errors++;
}
if(props0 !== true && props7 !== undefined){
if(props7 === true){
props0 = true;
}
else {
props0 = props0 || {};
Object.assign(props0, props7);
}
}
const _errs66 = errors;
let valid33 = true;
const _errs67 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
let missing8;
if(((data.route_id === undefined) || (!(func0.call(data, "route_id")))) && (missing8 = "route_id")){
const err48 = {};
if(vErrors === null){
vErrors = [err48];
}
else {
vErrors.push(err48);
}
errors++;
}
else {
if(data.route_id !== undefined && func0.call(data, "route_id")){
if("FIXTURE" !== data.route_id){
const err49 = {};
if(vErrors === null){
vErrors = [err49];
}
else {
vErrors.push(err49);
}
errors++;
}
}
}
}
var _valid8 = _errs67 === errors;
errors = _errs66;
if(vErrors !== null){
if(_errs66){
vErrors.length = _errs66;
}
else {
vErrors = null;
}
}
if(_valid8){
const _errs69 = errors;
if(data && typeof data == "object" && !Array.isArray(data)){
if(data.error !== undefined && func0.call(data, "error")){
let data25 = data.error;
if(data25 && typeof data25 == "object" && !Array.isArray(data25)){
if((data25.code === undefined) || (!(func0.call(data25, "code")))){
const err50 = {instancePath:instancePath+"/error",schemaPath:"#/allOf/8/then/properties/error/required",keyword:"required",params:{missingProperty: "code"},message:"must have required property '"+"code"+"'"};
if(vErrors === null){
vErrors = [err50];
}
else {
vErrors.push(err50);
}
errors++;
}
if(data25.code !== undefined && func0.call(data25, "code")){
if(!(data25.code === "INTERNAL_ERROR")){
const err51 = {instancePath:instancePath+"/error/code",schemaPath:"#/allOf/8/then/properties/error/properties/code/enum",keyword:"enum",params:{allowedValues: schema104.allOf[8].then.properties.error.properties.code.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err51];
}
else {
vErrors.push(err51);
}
errors++;
}
}
}
else {
const err52 = {instancePath:instancePath+"/error",schemaPath:"#/allOf/8/then/properties/error/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err52];
}
else {
vErrors.push(err52);
}
errors++;
}
}
}
var _valid8 = _errs69 === errors;
valid33 = _valid8;
if(valid33){
var props8 = {};
props8.error = true;
props8.route_id = true;
}
}
if(!valid33){
const err53 = {instancePath,schemaPath:"#/allOf/8/if",keyword:"if",params:{failingKeyword: "then"},message:"must match \"then\" schema"};
if(vErrors === null){
vErrors = [err53];
}
else {
vErrors.push(err53);
}
errors++;
}
if(props0 !== true && props8 !== undefined){
if(props8 === true){
props0 = true;
}
else {
props0 = props0 || {};
Object.assign(props0, props8);
}
}
if(data && typeof data == "object" && !Array.isArray(data)){
if((data.route_id === undefined) || (!(func0.call(data, "route_id")))){
const err54 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "route_id"},message:"must have required property '"+"route_id"+"'"};
if(vErrors === null){
vErrors = [err54];
}
else {
vErrors.push(err54);
}
errors++;
}
if((data.error === undefined) || (!(func0.call(data, "error")))){
const err55 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "error"},message:"must have required property '"+"error"+"'"};
if(vErrors === null){
vErrors = [err55];
}
else {
vErrors.push(err55);
}
errors++;
}
for(const key0 of Object.keys(data)){
if(!((key0 === "route_id") || (key0 === "error"))){
const err56 = {instancePath,schemaPath:"#/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key0},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err56];
}
else {
vErrors.push(err56);
}
errors++;
}
}
if(data.route_id !== undefined && func0.call(data, "route_id")){
let data27 = data.route_id;
if(!(((((((((data27 === "RUNS") || (data27 === "RUN_DETAIL")) || (data27 === "EVENTS")) || (data27 === "MATRIX")) || (data27 === "LEDGER")) || (data27 === "ARTIFACTS")) || (data27 === "D0")) || (data27 === "D1")) || (data27 === "FIXTURE"))){
const err57 = {instancePath:instancePath+"/route_id",schemaPath:"#/$defs/routeId/enum",keyword:"enum",params:{allowedValues: schema105.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err57];
}
else {
vErrors.push(err57);
}
errors++;
}
}
if(data.error !== undefined && func0.call(data, "error")){
let data28 = data.error;
if(data28 && typeof data28 == "object" && !Array.isArray(data28)){
if((data28.code === undefined) || (!(func0.call(data28, "code")))){
const err58 = {instancePath:instancePath+"/error",schemaPath:"#/$defs/error/required",keyword:"required",params:{missingProperty: "code"},message:"must have required property '"+"code"+"'"};
if(vErrors === null){
vErrors = [err58];
}
else {
vErrors.push(err58);
}
errors++;
}
if((data28.message === undefined) || (!(func0.call(data28, "message")))){
const err59 = {instancePath:instancePath+"/error",schemaPath:"#/$defs/error/required",keyword:"required",params:{missingProperty: "message"},message:"must have required property '"+"message"+"'"};
if(vErrors === null){
vErrors = [err59];
}
else {
vErrors.push(err59);
}
errors++;
}
for(const key1 of Object.keys(data28)){
if(!((key1 === "code") || (key1 === "message"))){
const err60 = {instancePath:instancePath+"/error",schemaPath:"#/$defs/error/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key1},message:"must NOT have additional properties"};
if(vErrors === null){
vErrors = [err60];
}
else {
vErrors.push(err60);
}
errors++;
}
}
if(data28.code !== undefined && func0.call(data28, "code")){
let data29 = data28.code;
if(!(((((data29 === "BAD_REQUEST") || (data29 === "NOT_FOUND")) || (data29 === "INVALID_CURSOR")) || (data29 === "VALIDATION_ERROR")) || (data29 === "INTERNAL_ERROR"))){
const err61 = {instancePath:instancePath+"/error/code",schemaPath:"#/$defs/error/properties/code/enum",keyword:"enum",params:{allowedValues: schema106.properties.code.enum},message:"must be equal to one of the allowed values"};
if(vErrors === null){
vErrors = [err61];
}
else {
vErrors.push(err61);
}
errors++;
}
}
if(data28.message !== undefined && func0.call(data28, "message")){
let data30 = data28.message;
if(typeof data30 === "string"){
if(func114(data30) < 1){
const err62 = {instancePath:instancePath+"/error/message",schemaPath:"#/$defs/error/properties/message/minLength",keyword:"minLength",params:{limit: 1},message:"must NOT have fewer than 1 characters"};
if(vErrors === null){
vErrors = [err62];
}
else {
vErrors.push(err62);
}
errors++;
}
}
else {
const err63 = {instancePath:instancePath+"/error/message",schemaPath:"#/$defs/error/properties/message/type",keyword:"type",params:{type: "string"},message:"must be string"};
if(vErrors === null){
vErrors = [err63];
}
else {
vErrors.push(err63);
}
errors++;
}
}
}
else {
const err64 = {instancePath:instancePath+"/error",schemaPath:"#/$defs/error/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err64];
}
else {
vErrors.push(err64);
}
errors++;
}
}
}
else {
const err65 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};
if(vErrors === null){
vErrors = [err65];
}
else {
vErrors.push(err65);
}
errors++;
}
validate101.errors = vErrors;
return errors === 0;
}
validate101.evaluated = {"props":true,"dynamicProps":false,"dynamicItems":false};
import type { ErrorObject } from 'ajv';
import type { V5ArtifactsRoot, V5D0Root, V5D1Root, V5EventsRoot, V5FixtureRoot, V5LedgerRoot, V5MatrixRoot, V5RunDetailRoot, V5RunsRoot, V5RouteId } from './kronosRlApiV2';

export type V5Validator<T> = ((data: unknown) => data is T) & {
  errors?: readonly ErrorObject[] | null;
};

export type V5RouteRootMap = {
  [K in V5RouteId]: Extract<V5ArtifactsRoot | V5D0Root | V5D1Root | V5EventsRoot | V5FixtureRoot | V5LedgerRoot | V5MatrixRoot | V5RunDetailRoot | V5RunsRoot, { route_id: K }>;
};

export type V5RouteDescriptorMap = {
  [K in V5RouteId]: {
    method: string;
    path: string;
    pathBindings: readonly string[];
    queryBindings: readonly string[];
    allowedErrors: readonly string[];
    validator: V5Validator<V5RouteRootMap[K]>;
  };
};

export const v5RouteDescriptors = {
  RUNS: {
    method: "GET",
    path: "/api/v5/rl/runs",
    pathBindings: [],
    queryBindings: [],
    allowedErrors: ["BAD_REQUEST","INVALID_CURSOR","INTERNAL_ERROR"],
    validator: validateRunsRoot as V5Validator<V5RunsRoot>,
  },
  RUN_DETAIL: {
    method: "GET",
    path: "/api/v5/rl/runs/{run_id}",
    pathBindings: ["run_id"],
    queryBindings: [],
    allowedErrors: ["NOT_FOUND","INTERNAL_ERROR"],
    validator: validateRunDetailRoot as V5Validator<V5RunDetailRoot>,
  },
  EVENTS: {
    method: "GET",
    path: "/api/v5/rl/runs/{run_id}/events",
    pathBindings: ["run_id"],
    queryBindings: [],
    allowedErrors: ["NOT_FOUND","INVALID_CURSOR","INTERNAL_ERROR"],
    validator: validateEventsRoot as V5Validator<V5EventsRoot>,
  },
  MATRIX: {
    method: "GET",
    path: "/api/v5/rl/matrix",
    pathBindings: [],
    queryBindings: ["run_id","revision"],
    allowedErrors: ["INTERNAL_ERROR"],
    validator: validateMatrixRoot as V5Validator<V5MatrixRoot>,
  },
  LEDGER: {
    method: "GET",
    path: "/api/v5/rl/ledger",
    pathBindings: [],
    queryBindings: ["run_id","revision"],
    allowedErrors: ["INVALID_CURSOR","INTERNAL_ERROR"],
    validator: validateLedgerRoot as V5Validator<V5LedgerRoot>,
  },
  ARTIFACTS: {
    method: "GET",
    path: "/api/v5/rl/artifacts",
    pathBindings: [],
    queryBindings: ["run_id","revision"],
    allowedErrors: ["INVALID_CURSOR","INTERNAL_ERROR"],
    validator: validateArtifactsRoot as V5Validator<V5ArtifactsRoot>,
  },
  D0: {
    method: "GET",
    path: "/api/v5/rl/d0",
    pathBindings: [],
    queryBindings: [],
    allowedErrors: ["INTERNAL_ERROR"],
    validator: validateD0Root as V5Validator<V5D0Root>,
  },
  D1: {
    method: "GET",
    path: "/api/v5/rl/d1",
    pathBindings: [],
    queryBindings: [],
    allowedErrors: ["INTERNAL_ERROR"],
    validator: validateD1Root as V5Validator<V5D1Root>,
  },
  FIXTURE: {
    method: "GET",
    path: "/api/v5/rl/fixture",
    pathBindings: [],
    queryBindings: [],
    allowedErrors: ["INTERNAL_ERROR"],
    validator: validateFixtureRoot as V5Validator<V5FixtureRoot>,
  },
} satisfies V5RouteDescriptorMap;

